import os
import re
import uuid
import zipfile
import structlog
import httpx
from typing import Optional

from config import get_settings
from canton.canton_client_v2 import CantonClientV2, make_sandbox_jwt

logger = structlog.get_logger()

_CANTON_NOT_RUNNING = """
Canton node is not reachable at {url}.

To start Canton Sandbox locally:
    daml sandbox

It starts on http://localhost:6865 by default.
For DevNet/MainNet set CANTON_ENVIRONMENT and the matching URL in backend/.env.
""".strip()


def _auth_header(canton_environment: str, act_as: list[str] | None = None) -> dict:
    if canton_environment == "sandbox":
        parties = act_as or ["issuer", "owner", "investor"]
        token = make_sandbox_jwt(parties)
        return {"Authorization": f"Bearer {token}"}
    token = os.environ.get("CANTON_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "CANTON_TOKEN env var is required for devnet/mainnet deployments. "
            "Set it in backend/.env as CANTON_TOKEN=<your-token>"
        )
    return {"Authorization": f"Bearer {token}"}


def _check_canton_reachable(canton_url: str, canton_environment: str) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                f"{canton_url}/v1/query",
                content=b'{"templateIds":[]}',
                headers={**_auth_header(canton_environment), "Content-Type": "application/json"},
            )
            if resp.status_code >= 500:
                raise ConnectionError(
                    f"Canton node returned {resp.status_code}. "
                    f"Node may be starting up — wait a moment and retry."
                )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise ConnectionError(_CANTON_NOT_RUNNING.format(url=canton_url))


def _upload_dar(client: httpx.Client, canton_url: str, dar_bytes: bytes, auth: dict) -> str:
    resp = client.post(
        f"{canton_url}/v1/packages",
        content=dar_bytes,
        headers={**auth, "Content-Type": "application/octet-stream"},
        timeout=180.0,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"DAR upload failed — HTTP {resp.status_code}: {resp.text[:400]}"
        )
    data = resp.json()
    package_id = (
        data.get("result")
        or data.get("packageId")
        or _compute_package_id(dar_bytes)
    )
    if isinstance(package_id, dict):
        package_id = package_id.get("packageId", _compute_package_id(dar_bytes))
    return str(package_id)


def _allocate_party(client: httpx.Client, canton_url: str, display_name: str, auth: dict) -> str:
    resp = client.post(
        f"{canton_url}/v1/parties/allocate",
        json={"displayName": display_name, "identifierHint": display_name.lower()},
        headers={**auth, "Content-Type": "application/json"},
        timeout=15.0,
    )
    logger.info("Party allocation response", status=resp.status_code, body=resp.text[:300])
    if resp.status_code in (200, 201):
        data = resp.json()
        identifier = (
            data.get("result", {}).get("identifier")
            or data.get("identifier")
        )
        if identifier:
            return identifier
    # If allocation fails (e.g. party already exists), try to fetch existing parties
    list_resp = client.get(
        f"{canton_url}/v1/parties",
        headers=auth,
        timeout=15.0,
    )
    if list_resp.status_code == 200:
        list_data = list_resp.json()
        for p in list_data.get("result", []):
            if p.get("displayName") == display_name or p.get("identifier", "").startswith(display_name.lower() + "::"):
                logger.info("Found existing party", name=display_name, id=p["identifier"])
                return p["identifier"]
    raise RuntimeError(f"Failed to allocate or find party '{display_name}': HTTP {resp.status_code} — {resp.text[:200]}")


def _create_contract(
    client: httpx.Client,
    canton_url: str,
    template_id: str,
    payload: dict,
    auth: dict,
) -> str:
    resp = client.post(
        f"{canton_url}/v1/create",
        json={"templateId": template_id, "payload": payload},
        headers={**auth, "Content-Type": "application/json"},
        timeout=60.0,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Contract creation failed — HTTP {resp.status_code}: {resp.text[:400]}"
        )
    data = resp.json()
    contract_id = (
        data.get("result", {}).get("contractId")
        or data.get("contractId")
    )
    if not contract_id:
        raise RuntimeError(f"No contractId in Canton response: {resp.text[:300]}")
    return contract_id


def run_deploy_agent(
    dar_path: str,
    structured_intent: dict,
    canton_url: str,
    canton_environment: str,
    party_id: str = "",
) -> dict:
    if not dar_path or not os.path.exists(dar_path):
        return {
            "success": False,
            "error":   f"DAR file not found: {dar_path}",
            "contract_id":   "",
            "package_id":    "",
            "explorer_link": "",
        }

    logger.info("Running deploy agent", dar_path=dar_path, environment=canton_environment, url=canton_url)

    try:
        _check_canton_reachable(canton_url, canton_environment)
    except (ConnectionError, EnvironmentError) as exc:
        logger.error("Canton not reachable", error=str(exc))
        return {
            "success": False,
            "error":   str(exc),
            "contract_id":   "",
            "package_id":    "",
            "explorer_link": "",
        }

    try:
        with open(dar_path, "rb") as f:
            dar_bytes = f.read()

        auth = _auth_header(canton_environment)

        # Step 1: Extract package ID from DAR manifest
        package_id = _extract_package_id_from_dar(dar_path)

        with httpx.Client() as client:
            # Step 2: Upload DAR
            _upload_dar(client, canton_url, dar_bytes, auth)
            logger.info("DAR uploaded", package_id=package_id)

            # Step 3: Allocate parties
            # If authenticated user has a party_id, use it as primary signatory
            parties = structured_intent.get("parties", ["issuer", "investor"])
            if len(parties) < 2:
                parties = parties + ["counterparty"]

            allocated = {}
            if party_id:
                # Use authenticated party as the first/primary signatory
                primary_name = parties[0] if parties else "issuer"
                allocated[primary_name] = party_id
                logger.info("Using authenticated party as primary signatory",
                            name=primary_name, party_id=party_id)
                # Allocate remaining parties (counterparties)
                for party_name in parties[1:4]:
                    allocated[party_name] = _allocate_party(client, canton_url, party_name, auth)
                    logger.info("Party allocated", name=party_name, id=allocated[party_name])
            else:
                for party_name in parties[:4]:
                    allocated[party_name] = _allocate_party(client, canton_url, party_name, auth)
                    logger.info("Party allocated", name=party_name, id=allocated[party_name])

            # Step 4: Read generated DAML code to parse template fields
            daml_code = _read_daml_source(dar_path)
            template_name = _extract_template_name(daml_code) if daml_code else None
            if not template_name:
                templates = structured_intent.get("daml_templates_needed", ["Main"])
                template_name = templates[0] if templates else "Main"

            # Step 5: Parse fields and build payload with proper defaults
            fields = _parse_template_fields(daml_code) if daml_code else []

            # Ensure enough distinct parties for all Party fields
            party_field_names = [f["name"] for f in fields if f["type"].strip() == "Party"]
            extra_needed = len(party_field_names) - len(allocated)
            if extra_needed > 0:
                _extra_names = [f"party{i+1}" for i in range(extra_needed)]
                # Prefer using field names as party hints for readability
                for idx, fname in enumerate(party_field_names):
                    if fname not in allocated:
                        hint = fname.lower().replace("_", "")
                        try:
                            allocated[fname] = _allocate_party(client, canton_url, hint, auth)
                            logger.info("Extra party allocated", name=fname, id=allocated[fname])
                        except Exception:
                            pass

            payload = _build_payload(fields, allocated)

            # If no fields found, use party mapping directly
            if not payload:
                payload = dict(allocated)

            # Build fully-qualified template ID
            module_name = _extract_module_name(daml_code) if daml_code else "Main"
            if package_id:
                template_id = f"{package_id}:{module_name}:{template_name}"
            else:
                template_id = f"{module_name}:{template_name}"

            logger.info("Creating contract", template_id=template_id, payload=payload)

            # Collect ALL party IDs used in the payload (not just allocated map)
            all_party_ids = set(allocated.values())
            for v in payload.values():
                if isinstance(v, str) and "::" in v:
                    all_party_ids.add(v)

            # Regenerate JWT with all party IDs for sandbox
            if canton_environment == "sandbox":
                from canton.canton_client_v2 import make_sandbox_jwt
                token = make_sandbox_jwt(list(all_party_ids))
                auth = {"Authorization": f"Bearer {token}"}
                logger.info("JWT regenerated with parties", party_ids=list(all_party_ids))

            # Step 6: Create contract
            contract_id = _create_contract(
                client,
                canton_url,
                template_id,
                payload,
                auth,
            )
            logger.info("Contract created", contract_id=contract_id)

            # Step 7: Verify contract on ledger
            verified = _verify_contract(client, canton_url, contract_id, template_id, auth)
            if verified:
                logger.info("Contract verified on ledger", contract_id=contract_id)
            else:
                logger.warning("Contract verification failed, but contract was created", contract_id=contract_id)

        if canton_environment == "sandbox":
            explorer_link = f"http://localhost:7575/contract/{contract_id}"
        elif canton_environment == "devnet":
            explorer_link = f"https://canton.network/explorer/contract/{contract_id}"
        else:
            explorer_link = f"https://main.canton.network/explorer/contract/{contract_id}"

        return {
            "success":       True,
            "contract_id":   contract_id,
            "package_id":    package_id,
            "template_id":   template_id,
            "explorer_link": explorer_link,
            "environment":   canton_environment,
            "parties":       allocated,
        }

    except RuntimeError as exc:
        logger.error("Deploy failed", error=str(exc))
        return {
            "success": False,
            "error":   str(exc),
            "contract_id":   "",
            "package_id":    "",
            "explorer_link": "",
        }
    except Exception as exc:
        logger.error("Unexpected deploy error", error=str(exc))
        return {
            "success": False,
            "error":   f"Unexpected error: {exc}",
            "contract_id":   "",
            "package_id":    "",
            "explorer_link": "",
        }


def _read_daml_source(dar_path: str) -> str:
    """Read the Main.daml source from the project directory next to the DAR."""
    try:
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(dar_path)))
        main_daml = os.path.join(project_dir, "daml", "Main.daml")
        if os.path.exists(main_daml):
            with open(main_daml, "r") as f:
                return f.read()
    except Exception:
        pass
    return ""


def _verify_contract(client: httpx.Client, canton_url: str, contract_id: str, template_id: str, auth: dict) -> bool:
    """Verify contract exists on the ledger via POST /v1/query."""
    try:
        body = {}
        if template_id:
            body["templateIds"] = [template_id]
        resp = client.post(
            f"{canton_url}/v1/query",
            json=body,
            headers={**auth, "Content-Type": "application/json"},
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("result", [])
            for entry in results:
                if entry.get("contractId") == contract_id:
                    return True
        return False
    except Exception as e:
        logger.warning("Verification query failed", error=str(e))
        return False


def _compute_package_id(dar_bytes: bytes) -> str:
    pass  # replaced by _extract_package_id_from_dar


def _extract_package_id_from_dar(dar_path: str) -> str:
    """Read the main DALF package hash from META-INF/MANIFEST.MF inside the DAR zip."""
    try:
        with zipfile.ZipFile(dar_path) as z:
            manifest = z.read("META-INF/MANIFEST.MF").decode("utf-8")
        # Reconstruct multi-line folded value (lines starting with a space are continuations)
        lines: list[str] = []
        for raw in manifest.splitlines():
            if raw.startswith(" ") and lines:
                lines[-1] += raw[1:]
            else:
                lines.append(raw)
        for line in lines:
            if line.startswith("Main-Dalf:"):
                main_dalf = line.split(":", 1)[1].strip()
                # Pattern:  {dir}-{hash}/{filename}-{hash}.dalf
                # Extract 64-char hex hash from filename
                import re as _re
                m = _re.search(r"[/\\]([0-9a-f]{64})\.dalf$", main_dalf)
                if m:
                    return m.group(1)
                # Fallback: any 64-char hex run in the path
                m = _re.search(r"[0-9a-f]{64}", main_dalf)
                if m:
                    return m.group(0)
    except Exception as exc:
        logger.warning("Could not extract package ID from DAR manifest", error=str(exc))
    return ""


# ---------------------------------------------------------------------------
# Sandbox-based async deploy agent using Canton v2 API
# ---------------------------------------------------------------------------

def _parse_template_fields(daml_code: str) -> list[dict]:
    template_match = re.search(
        r"template\s+\w+\s+with\s+(.*?)\s+where",
        daml_code,
        re.DOTALL,
    )
    if not template_match:
        return []

    fields = []
    for line in template_match.group(1).split("\n"):
        line = line.strip()
        if ":" in line:
            name, field_type = line.split(":", 1)
            fields.append({"name": name.strip(), "type": field_type.strip()})
    return fields


def _build_payload(fields: list[dict], party_values: dict) -> dict:
    payload = {}
    party_ids = list(party_values.values())
    used_party_ids: set[str] = set()
    party_idx = 0
    numeric_counter = 0
    date_counter = 0

    for field in fields:
        name = field["name"]
        ftype = field["type"].strip()

        if name in party_values:
            payload[name] = party_values[name]
            used_party_ids.add(party_values[name])
        elif ftype == "Party":
            # Ensure each Party field gets a DISTINCT party ID
            # (many ensure clauses check party1 /= party2)
            assigned = None
            for i in range(len(party_ids)):
                candidate = party_ids[(party_idx + i) % len(party_ids)]
                if candidate not in used_party_ids:
                    assigned = candidate
                    party_idx = (party_idx + i + 1) % len(party_ids)
                    break
            if assigned is None and party_ids:
                # All parties used — fall back to round-robin
                assigned = party_ids[party_idx % len(party_ids)]
                party_idx += 1
            if assigned:
                payload[name] = assigned
                used_party_ids.add(assigned)
            else:
                payload[name] = name
        elif ftype in ("Decimal", "Numeric") or ftype.startswith("Numeric "):
            # Use positive, distinct values (ensure clauses often check > 0)
            numeric_counter += 1
            payload[name] = f"{100.0 * numeric_counter}"
        elif ftype == "Int" or ftype == "Int64":
            numeric_counter += 1
            payload[name] = max(1, numeric_counter)
        elif ftype == "Text":
            payload[name] = f"sample-{name}"
        elif ftype == "Date":
            # Use distinct future dates (ensure clauses often check end > start)
            date_counter += 1
            payload[name] = f"2025-{min(date_counter, 12):02d}-15"
        elif ftype in ("Time", "UTCTime"):
            date_counter += 1
            payload[name] = f"2025-{min(date_counter, 12):02d}-15T00:00:00Z"
        elif ftype == "Bool":
            payload[name] = True
        elif ftype.startswith("["):
            payload[name] = []
        elif ftype.startswith("Optional"):
            payload[name] = None
        else:
            payload[name] = f"sample-{name}"
    return payload


def _extract_template_name(daml_code: str) -> str | None:
    match = re.search(r"^template\s+(\w+)", daml_code, re.MULTILINE)
    return match.group(1) if match else None


def _extract_module_name(daml_code: str) -> str | None:
    match = re.search(r"^module\s+(\S+)\s+where", daml_code, re.MULTILINE)
    return match.group(1) if match else None


async def run_deploy_agent_sandbox(
    sandbox,
    project_name: str,
    parties: list[str],
    canton_url: str,
    auth_token: Optional[str] = None,
) -> dict:
    logger.info("Running sandbox deploy agent", project_name=project_name, canton_url=canton_url)

    client = CantonClientV2(canton_url, auth_token)

    dar_relative = f".daml/dist/{project_name}-0.0.1.dar"
    dar_absolute = sandbox.get_absolute_path(dar_relative)

    # Step 1: Extract real package ID from DAR manifest before upload
    package_id = _extract_package_id_from_dar(dar_absolute)

    success, error = await client.upload_dar(dar_absolute)
    if not success:
        logger.error("DAR upload failed", error=error)
        return {"success": False, "error": f"DAR upload failed: {error}", "contract_id": "", "package_id": ""}

    logger.info("DAR uploaded", package_id=package_id)

    # Step 2: Allocate parties
    allocated: dict[str, str] = {}
    for party_hint in parties:
        ok, party_id, err = await client.allocate_party(party_hint)
        if not ok:
            logger.error("Party allocation failed", hint=party_hint, error=err)
            return {"success": False, "error": f"Party allocation failed for {party_hint}: {err}", "contract_id": "", "package_id": package_id}
        allocated[party_hint] = party_id
        logger.info("Party allocated", hint=party_hint, party_id=party_id)

    # Regenerate JWT with real party IDs so the ledger authorises the actAs parties
    full_party_ids = list(allocated.values())
    if full_party_ids:
        client.set_token(make_sandbox_jwt(full_party_ids))

    # Step 3: Parse template fields from Main.daml
    try:
        daml_code = await sandbox.files.read("daml/Main.daml")
    except FileNotFoundError:
        return {"success": False, "error": "daml/Main.daml not found in sandbox", "contract_id": "", "package_id": package_id}

    template_name = _extract_template_name(daml_code) or project_name
    fields = _parse_template_fields(daml_code)

    # Step 4: Build payload — use fully-qualified packageId:Module:Template
    payload = _build_payload(fields, allocated)
    module_name = _extract_module_name(daml_code) or "Main"
    template_id = f"{package_id}:{module_name}:{template_name}" if package_id else f"{module_name}:{template_name}"
    acting_party = list(allocated.values())[0] if allocated else ""

    logger.info("Creating contract", template_id=template_id, acting_party=acting_party)

    # Step 5: Create contract
    ok, contract_id, err = await client.create_contract(template_id, payload, acting_party)
    if not ok:
        logger.error("Contract creation failed", error=err)
        return {"success": False, "error": f"Contract creation failed: {err}", "contract_id": "", "package_id": package_id}

    logger.info("Contract created", contract_id=contract_id)

    # Step 6: Verify contract exists
    ok, err = await client.verify_contract(contract_id, template_id=template_id)
    if not ok:
        logger.warning("Contract verification failed", error=err)

    return {
        "success": True,
        "contract_id": contract_id,
        "package_id": package_id,
        "parties": allocated,
        "template_id": template_id,
    }
