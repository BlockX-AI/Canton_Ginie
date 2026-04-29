import hashlib
import json
import os
import re
import time
import zipfile
import structlog
import httpx
from decimal import Decimal, ROUND_DOWN
from typing import Optional

from config import get_settings
from canton.canton_client_v2 import CantonClientV2, make_sandbox_jwt

logger = structlog.get_logger()

_CANTON_NOT_RUNNING = """
Canton node is not reachable at {url}.

To start Canton Sandbox locally (in-memory):
    canton sandbox --config canton-sandbox-memory.conf

Or with PostgreSQL persistence:
    canton sandbox --config canton-sandbox.conf

The HTTP JSON API will be available on http://localhost:7575 once started.
For DevNet/MainNet set CANTON_ENVIRONMENT and the matching URL in backend/.env.
""".strip()


def _auth_header(canton_environment: str, act_as: list[str] | None = None) -> dict:
    if canton_environment == "sandbox":
        parties = act_as or ["sandbox-admin"]
        token = make_sandbox_jwt(parties)
        return {"Authorization": f"Bearer {token}"}
    token = get_settings().canton_token
    if not token:
        raise EnvironmentError(
            "CANTON_TOKEN is required for devnet/mainnet deployments. "
            "Set it in backend/.env.ginie as CANTON_TOKEN=<your-token>"
        )
    return {"Authorization": f"Bearer {token}"}


def _check_canton_reachable(canton_url: str, canton_environment: str) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{canton_url}/livez")
            if resp.status_code >= 500:
                raise ConnectionError(
                    f"Canton node returned {resp.status_code} on /livez. "
                    "Node may be starting up — wait a moment and retry."
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
    logger.info("DAR upload response", response_keys=list(data.keys()), result_type=type(data.get("result")).__name__)
    # Canton JSON API returns {"result": 1, "status": 200} on success — no package ID.
    # Only use result if it looks like a real package hash (64-char hex string).
    result = data.get("result")
    if isinstance(result, str) and len(result) == 64:
        return result
    if isinstance(result, dict):
        pkg = result.get("packageId", "")
        if isinstance(pkg, str) and len(pkg) == 64:
            return pkg
    pkg = data.get("packageId", "")
    if isinstance(pkg, str) and len(pkg) == 64:
        return pkg
    # No usable package ID from upload response
    return ""


def _wait_for_package_vetting(
    client: httpx.Client,
    canton_url: str,
    package_id: str,
    auth: dict,
    max_attempts: int = 15,
    delay: float = 2.0,
) -> bool:
    """Poll GET /v1/packages until the uploaded package is visible on the ledger.

    Canton vets packages automatically on upload but the topology transaction
    needs a short time to propagate to the domain.  If we create a contract
    before vetting completes we get NO_DOMAIN_FOR_SUBMISSION.
    """
    if not package_id:
        # No package ID to check — just do a fixed wait
        logger.warning("No package ID available, using fixed delay for vetting")
        time.sleep(5.0)
        return True

    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.get(
                f"{canton_url}/v1/packages",
                headers={**auth, "Content-Type": "application/json"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                packages = data.get("result", [])
                if package_id in packages:
                    logger.info("Package vetting confirmed", package_id=package_id[:16], attempt=attempt)
                    return True
        except Exception as exc:
            logger.warning("Package vetting check failed", attempt=attempt, error=str(exc))

        logger.info("Waiting for package vetting", package_id=package_id[:16], attempt=attempt, max=max_attempts)
        time.sleep(delay)

    logger.warning("Package vetting not confirmed after retries, proceeding anyway", package_id=package_id[:16])
    return False


def _sanitize_identifier_hint(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9-]", "-", name.lower())
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    return sanitized or "party"


def _allocate_party(client: httpx.Client, canton_url: str, display_name: str, auth: dict) -> str:
    hint = _sanitize_identifier_hint(display_name)
    resp = client.post(
        f"{canton_url}/v1/parties/allocate",
        json={"displayName": display_name, "identifierHint": hint},
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


_TRANSIENT_LEDGER_MARKERS = (
    # Package was uploaded but the vetting topology tx hasn't propagated
    # to all informee participants on the domain yet.
    "NO_DOMAIN_FOR_SUBMISSION",
    "domainsNotUsed",
    "Some packages are not known to all informees",
    # Newly-allocated party not yet observable on the domain.
    "PARTY_NOT_KNOWN_ON_LEDGER",
    "UNKNOWN_INFORMEES",
    "UNKNOWN_SUBMITTERS",
    # Generic Canton "try again" responses we've observed under load.
    "REQUEST_TIME_OUT",
    "ABORTED",
)

def _is_transient_ledger_error(body: str) -> bool:
    return any(m in body for m in _TRANSIENT_LEDGER_MARKERS)


def _build_command_id(template_id: str, payload: dict, acting_parties: list[str] | None) -> str:
    """Derive a deterministic ``commandId`` from the business inputs.

    Canton has a command-deduplication window (default 24h): a
    ``commandId`` submitted twice inside the window is silently
    de-duplicated and returns the original transaction. With a random
    UUID, every retry creates a duplicate contract; with a hash of the
    business keys, retries are natural no-ops.

    The hash inputs:
      * ``template_id``  \u2014 the fully-qualified Canton template ID.
      * ``payload``      \u2014 canonical JSON of the create arguments.
      * ``acting_parties`` \u2014 sorted list of submitter parties.

    Two distinct deploys (different parties OR different payload) get
    different IDs; the same deploy retried gets the same ID and Canton
    dedupes for us. The ``ginie-`` prefix lets ledger operators trace
    submissions back to this generator.
    """
    canonical = json.dumps(
        {
            "template_id": template_id,
            "payload":     payload,
            "act_as":      sorted(acting_parties or []),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"ginie-deploy-{digest[:24]}"


def _create_contract(
    client: httpx.Client,
    canton_url: str,
    template_id: str,
    payload: dict,
    auth: dict,
    acting_parties: list[str] | None = None,
) -> str:
    command_id = _build_command_id(template_id, payload, acting_parties)
    body: dict = {
        "templateId": template_id,
        "payload": payload,
        "meta": {
            "commandId": command_id,
        },
    }
    if acting_parties:
        body["meta"]["actAs"] = acting_parties

    # Retry on transient ledger errors. Canton package-vetting and party
    # allocation are eventually-consistent topology transactions; the create
    # can race ahead of the domain's view by a few seconds. We back off
    # geometrically up to ~45s before giving up.
    delays = [0.0, 2.0, 4.0, 6.0, 10.0, 14.0]
    last_status = 0
    last_body = ""
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            logger.info(
                "Retrying contract creation after transient ledger error",
                attempt=attempt,
                delay=delay,
                marker=last_body[:200],
            )
            time.sleep(delay)
        try:
            resp = client.post(
                f"{canton_url}/v1/create",
                json=body,
                headers={**auth, "Content-Type": "application/json"},
                timeout=60.0,
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            last_status = 0
            last_body = f"network error: {exc}"
            continue

        if resp.status_code in (200, 201):
            data = resp.json()
            contract_id = (
                data.get("result", {}).get("contractId")
                or data.get("contractId")
            )
            if not contract_id:
                raise RuntimeError(
                    f"No contractId in Canton response: {resp.text[:300]}"
                )
            return contract_id

        last_status = resp.status_code
        last_body = resp.text[:600]
        if not _is_transient_ledger_error(last_body):
            break

    raise RuntimeError(
        f"Contract creation failed — HTTP {last_status}: {last_body}"
    )


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

        # Step 1: Extract package ID from DAR manifest (fallback)
        manifest_package_id = _extract_package_id_from_dar(dar_path)

        with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=10.0)) as client:
            # Step 2: Upload DAR — use package ID from Canton response
            upload_package_id = _upload_dar(client, canton_url, dar_bytes, auth)
            package_id = upload_package_id or manifest_package_id
            logger.info("DAR uploaded", package_id=package_id, source="upload" if upload_package_id else "manifest")

            # Step 2b: Wait for package vetting to propagate to domain
            _wait_for_package_vetting(client, canton_url, package_id, auth)

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

            # If needs_proposal, deploy the Proposal template instead of the core
            if structured_intent.get("needs_proposal") and daml_code:
                proposal_name = f"{template_name}Proposal"
                proposal_fields = _parse_template_fields(daml_code, proposal_name)
                if proposal_fields:
                    logger.info("Deploying proposal template instead of core",
                                core=template_name, proposal=proposal_name)
                    template_name = proposal_name

            # Step 5: Parse fields and build payload with proper defaults
            fields = _parse_template_fields(daml_code, template_name) if daml_code else []

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

            payload = _build_payload(fields, allocated, daml_code=daml_code, template_name=template_name)

            # If no fields found, use party mapping directly
            if not payload:
                payload = dict(allocated)

            # Build fully-qualified template ID. Short-form
            # ``Module:Template`` works on a single-version sandbox but
            # is ambiguous on production participants where multiple
            # package versions can be loaded simultaneously \u2014 Canton
            # may pick the wrong version or reject the command. We
            # ALWAYS prefer ``<packageId>:Module:Template`` and warn
            # loudly when forced to fall back.
            module_name = (_extract_module_name(daml_code) if daml_code else None) or "Main"
            if package_id:
                template_id = f"{package_id}:{module_name}:{template_name}"
            else:
                template_id = f"{module_name}:{template_name}"
                logger.error(
                    "Falling back to SHORT-FORM template ID \u2014 multi-version "
                    "production participants may pick the wrong package",
                    module=module_name,
                    template=template_name,
                )
            logger.info("Template ID resolved", module=module_name, template=template_name, template_id=template_id, full_form=bool(package_id))

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
                acting_parties=list(all_party_ids),
            )
            logger.info("Contract created", contract_id=contract_id)

            # Step 7: Verify contract on ledger
            verified = _verify_contract(client, canton_url, contract_id, template_id, auth)
            if verified:
                logger.info("Contract verified on ledger", contract_id=contract_id)
            else:
                logger.warning("Contract verification failed, but contract was created", contract_id=contract_id)

        if canton_environment == "sandbox":
            explorer_link = f"http://localhost:7575/v1/query#contractId={contract_id}"
        elif canton_environment == "devnet":
            explorer_link = f"https://scan.sv.canton.network/#/transactions/{contract_id}"
        else:
            explorer_link = f"https://scan.sv.canton.network/#/transactions/{contract_id}"

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
    """Read DAML source from the project directory next to the DAR.

    Scans all .daml files in the daml/ directory (not just Main.daml)
    so that contracts with non-Main module names are found correctly.
    """
    try:
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(dar_path)))
        daml_dir = os.path.join(project_dir, "daml")
        if not os.path.isdir(daml_dir):
            return ""
        parts: list[str] = []
        for fname in sorted(os.listdir(daml_dir)):
            if fname.endswith(".daml"):
                with open(os.path.join(daml_dir, fname), "r") as f:
                    parts.append(f.read())
        return "\n".join(parts)
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


def _extract_package_id_from_dar(dar_path: str) -> str:
    """Read the main DALF package hash from a DAR zip.

    Strategy:
    1. Parse META-INF/MANIFEST.MF for Main-Dalf entry
    2. Fallback: scan zip entries for .dalf files and extract 64-char hex hash
    """
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
                    logger.info("DAR manifest Main-Dalf", main_dalf=main_dalf)
                    # Pattern:  {dir}-{hash}/{filename}-{hash}.dalf
                    m = re.search(r"[/\\]([0-9a-f]{64})\.dalf$", main_dalf)
                    if m:
                        return m.group(1)
                    # Fallback: any 64-char hex run in the path
                    m = re.search(r"[0-9a-f]{64}", main_dalf)
                    if m:
                        return m.group(0)

            # Strategy 2: scan zip entries for .dalf files
            for name in z.namelist():
                if name.endswith(".dalf") and "META-INF" not in name:
                    m = re.search(r"([0-9a-f]{64})", name)
                    if m:
                        logger.info("Package ID from DALF filename", dalf=name, pkg=m.group(1))
                        return m.group(1)
    except Exception as exc:
        logger.warning("Could not extract package ID from DAR", error=str(exc))
    return ""


# ---------------------------------------------------------------------------
# Sandbox-based async deploy agent using Canton v2 API
# ---------------------------------------------------------------------------

def _parse_template_fields(daml_code: str, template_name: str | None = None) -> list[dict]:
    """Parse fields from a template's ``with`` block.

    If *template_name* is given, parse that specific template;
    otherwise parse the first template found.
    """
    if template_name:
        pattern = rf"template\s+{re.escape(template_name)}\s+with\s+(.*?)\s+where"
    else:
        pattern = r"template\s+\w+\s+with\s+(.*?)\s+where"
    template_match = re.search(pattern, daml_code, re.DOTALL)
    if not template_match:
        return []

    fields = []
    for line in template_match.group(1).split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("--"):
            name, field_type = line.split(":", 1)
            fields.append({"name": name.strip(), "type": field_type.strip()})
    return fields


def _extract_ensure_text_values(daml_code: str, template_name: str | None = None) -> dict[str, str]:
    """Parse ensure clauses to find valid string literals for Text fields.

    For example, ``ensure status == "Pending"`` yields {"status": "Pending"}.
    Also handles ``status == "Pending" || status == "Active"`` — picks the first.
    """
    hints: dict[str, str] = {}
    if not daml_code:
        return hints

    # Find the ensure block for the target template
    if template_name:
        pat = rf"template\s+{re.escape(template_name)}\s+.*?\bensure\s+(.*?)\n\s*\n"
    else:
        pat = r"\bensure\s+(.*?)\n\s*\n"
    m = re.search(pat, daml_code, re.DOTALL)
    if not m:
        # Try alternate: ensure up to next choice/key/deriving line
        if template_name:
            pat2 = rf"template\s+{re.escape(template_name)}\s+.*?\bensure\s+(.*?)(?=\n\s+(?:choice|key|deriving)\b)"
        else:
            pat2 = r"\bensure\s+(.*?)(?=\n\s+(?:choice|key|deriving)\b)"
        m = re.search(pat2, daml_code, re.DOTALL)
    if not m:
        return hints

    ensure_text = m.group(1)
    # Find patterns like:  fieldName == "Value"
    for field_match in re.finditer(r'(\w+)\s*==\s*"([^"]+)"', ensure_text):
        fname = field_match.group(1)
        fval = field_match.group(2)
        if fname not in hints:
            hints[fname] = fval
    logger.info("Ensure text hints extracted", hints=hints)
    return hints


def _extract_ensure_numeric_values(daml_code: str, template_name: str | None = None) -> dict[str, str]:
    """Parse ensure clauses to find numeric equality constraints.

    For example, ``ensure amount == 100.0`` yields {"amount": "100.0"}.
    Also handles ``quantity == 50`` (integers).
    """
    hints: dict[str, str] = {}
    if not daml_code:
        return hints

    # Find the ensure block for the target template
    if template_name:
        pat = rf"template\s+{re.escape(template_name)}\s+.*?\bensure\s+(.*?)\n\s*\n"
    else:
        pat = r"\bensure\s+(.*?)\n\s*\n"
    m = re.search(pat, daml_code, re.DOTALL)
    if not m:
        if template_name:
            pat2 = rf"template\s+{re.escape(template_name)}\s+.*?\bensure\s+(.*?)(?=\n\s+(?:choice|key|deriving)\b)"
        else:
            pat2 = r"\bensure\s+(.*?)(?=\n\s+(?:choice|key|deriving)\b)"
        m = re.search(pat2, daml_code, re.DOTALL)
    if not m:
        return hints

    ensure_text = m.group(1)
    # Match exact equality ONLY:  fieldName == 100.0  or  fieldName == 50
    # We intentionally skip > / >= constraints because the default payload
    # values (e.g. 1000.0 for Decimal) already satisfy them.  Extracting
    # the bound (e.g. 0.0 from "amount > 0.0") would set the field to
    # exactly the bound, which violates strict ">" checks.
    for field_match in re.finditer(r'(\w+)\s*==\s*([0-9]+(?:\.[0-9]+)?)', ensure_text):
        fname = field_match.group(1)
        fval = field_match.group(2)
        if fname not in hints:
            hints[fname] = fval
    logger.info("Ensure numeric hints extracted", hints=hints)
    return hints


def _build_payload(fields: list[dict], party_values: dict, daml_code: str = "", template_name: str | None = None) -> dict:
    payload = {}
    party_ids = list(party_values.values())
    used_party_ids: set[str] = set()
    party_idx = 0
    numeric_counter = 0
    date_counter = 0

    # Extract valid text values from ensure clauses to satisfy preconditions
    ensure_hints = _extract_ensure_text_values(daml_code, template_name) if daml_code else {}
    numeric_hints = _extract_ensure_numeric_values(daml_code, template_name) if daml_code else {}

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
            numeric_counter += 1
            if name in numeric_hints:
                payload[name] = str(Decimal(numeric_hints[name]).quantize(Decimal("0.0000000000"), rounding=ROUND_DOWN))
            else:
                name_lower = name.lower()
                if "rate" in name_lower or "percent" in name_lower or "ratio" in name_lower:
                    val = Decimal("0.05") * numeric_counter
                else:
                    val = Decimal("1000.00") * numeric_counter
                payload[name] = str(val.quantize(Decimal("0.0000000000"), rounding=ROUND_DOWN))
        elif ftype == "Int" or ftype == "Int64":
            numeric_counter += 1
            if name in numeric_hints:
                payload[name] = int(numeric_hints[name])
            else:
                payload[name] = max(1, numeric_counter)
        elif ftype == "Text":
            # Use ensure-clause hints first, then smart defaults for common names
            if name in ensure_hints:
                payload[name] = ensure_hints[name]
            else:
                name_lower = name.lower()
                if name_lower in ("status", "state"):
                    payload[name] = "Pending"
                elif name_lower in ("phase", "stage"):
                    payload[name] = "Initial"
                elif name_lower in ("type", "category", "kind"):
                    payload[name] = "Standard"
                elif name_lower in ("currency", "ccy"):
                    payload[name] = "USD"
                elif "name" in name_lower:
                    payload[name] = f"Sample {name}"
                elif "desc" in name_lower or "reason" in name_lower or "note" in name_lower:
                    payload[name] = f"Auto-generated {name}"
                else:
                    payload[name] = f"sample-{name}"
        elif ftype == "Date":
            # Use distinct future dates (ensure clauses often check date > now)
            date_counter += 1
            payload[name] = f"2027-{min(date_counter + 5, 12):02d}-15"
        elif ftype in ("Time", "UTCTime"):
            date_counter += 1
            payload[name] = f"2027-{min(date_counter + 5, 12):02d}-15T00:00:00Z"
        elif ftype == "Bool":
            payload[name] = True
        elif ftype.startswith("["):
            # Daml templates almost always reject empty lists in `ensure`
            # (e.g. `not (null voters)`, `length signers > 0`). Seed lists
            # with at least one valid element keyed off the inner type.
            inner = ftype[1:-1].strip() if ftype.endswith("]") else ""
            if inner == "Party" and party_ids:
                # Prefer parties not yet used by this payload, fall back to
                # all allocated parties so voters / observers / signers etc.
                # come pre-populated with the deploying user's identities.
                unused = [pid for pid in party_ids if pid not in used_party_ids]
                payload[name] = unused if unused else list(party_ids)
            elif inner == "Text":
                payload[name] = [f"sample-{name}-1"]
            elif inner in ("Int", "Int64"):
                payload[name] = [1]
            elif inner in ("Decimal", "Numeric") or inner.startswith("Numeric "):
                payload[name] = ["100.0000000000"]
            elif inner == "Bool":
                payload[name] = [True]
            else:
                # Unknown element type — empty is the safest fallback.
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
