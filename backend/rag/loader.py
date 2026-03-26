import os
import re
import json
import glob
import structlog
from pathlib import Path
from typing import Optional

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Skiplist — files known to be broken or unhelpful
# ---------------------------------------------------------------------------

_SKIPLIST_FILE = os.path.join(os.path.dirname(__file__), "daml_examples", "_skiplist.txt")


def _load_skiplist() -> set[str]:
    if os.path.exists(_SKIPLIST_FILE):
        return set(Path(_SKIPLIST_FILE).read_text(encoding="utf-8").strip().splitlines())
    return set()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_daml_examples(examples_dir: str | None = None) -> list[dict]:
    """
    Recursively load .daml files from examples_dir and all subdirectories.
    Returns a list of document dicts ready for vector store insertion.

    Each document contains:
        content, source, file_name, contract_type, chunk_type, category,
        complexity, has_interfaces, metadata (flat dict for ChromaDB)
    """
    if examples_dir is None:
        examples_dir = os.path.join(os.path.dirname(__file__), "daml_examples")

    skiplist = _load_skiplist()
    documents: list[dict] = []
    file_count = 0

    # Recursively walk all subdirectories
    examples_path = Path(examples_dir)
    daml_files = sorted(examples_path.rglob("*.daml"))

    for file_path in daml_files:
        rel = str(file_path.relative_to(examples_path))

        # Skip quarantine and hidden dirs
        parts = file_path.relative_to(examples_path).parts
        if any(p.startswith(".") or p == "quarantine" for p in parts):
            continue
        if rel in skiplist or file_path.name in skiplist:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.error("Failed to read Daml file", file=str(file_path), error=str(e))
            continue

        if len(content.strip()) < 20:
            continue

        file_name = file_path.stem
        category = _infer_category(file_path, examples_path, content)
        contract_type = _infer_contract_type(file_name, content, category)
        meta_info = _extract_file_metadata(content)

        chunks = _chunk_daml_file(content, file_name)
        for chunk in chunks:
            metadata = {
                "source":         str(file_path),
                "file_name":      file_name,
                "contract_type":  contract_type,
                "chunk_type":     chunk["type"],
                "category":       category,
                "complexity":     meta_info["complexity"],
                "has_interfaces": str(meta_info["has_interfaces"]),
                "template_count": str(meta_info["template_count"]),
                "choice_count":   str(meta_info["choice_count"]),
                "line_count":     str(meta_info["line_count"]),
            }
            documents.append({
                "content":       chunk["content"],
                "source":        str(file_path),
                "file_name":     file_name,
                "contract_type": contract_type,
                "chunk_type":    chunk["type"],
                "category":      category,
                "complexity":    meta_info["complexity"],
                "has_interfaces": meta_info["has_interfaces"],
                "metadata":      metadata,
            })

        file_count += 1

    logger.info("Loaded Daml examples", count=len(documents), files=file_count)
    return documents


# ---------------------------------------------------------------------------
# Category inference (from subdirectory or content analysis)
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "defi":            ["swap", "amm", "lending", "borrow", "liquidity", "pool", "dex", "yield", "stake"],
    "securities":      ["bond", "equity", "option", "future", "derivative", "coupon", "maturity", "instrument"],
    "payments":        ["cash", "payment", "invoice", "remittance", "settlement", "transfer", "payout"],
    "supply_chain":    ["supply", "shipment", "logistics", "tracking", "provenance", "warehouse"],
    "governance":      ["vote", "voting", "proposal", "governance", "ballot", "quorum", "dao"],
    "identity":        ["kyc", "credential", "identity", "attestation", "verification"],
    "nft":             ["nft", "token", "collectible", "marketplace", "royalty", "mint"],
    "token_standards": ["cip56", "holding", "transferfactory", "transferinstruction", "amulet", "splice"],
    "daml_finance":    ["daml.finance", "instrument", "lifecycle", "claim", "account", "factory"],
    "interfaces":      ["interface", "implements", "viewtype", "requires"],
    "propose_accept":  ["propose", "accept", "approval", "workflow", "request", "confirm"],
    "testing":         ["script do", "test", "scenario"],
    "utilities":       ["util", "helper", "lib", "common", "types"],
}


def _infer_category(file_path: Path, examples_root: Path, content: str) -> str:
    """Infer category from subdirectory name first, then content analysis."""
    rel_parts = file_path.relative_to(examples_root).parts
    if len(rel_parts) > 1:
        # First directory component is the category
        subdir = rel_parts[0].lower()
        # Check if it's a known category
        known = set(_CATEGORY_KEYWORDS.keys()) | {"original", "sdk_templates"}
        if subdir in known:
            return subdir

    # Fallback: content-based classification
    text = (content + " " + file_path.name).lower()
    scores: dict[str, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)
    return "utilities"


# ---------------------------------------------------------------------------
# Contract type inference (expanded from original 8-type map)
# ---------------------------------------------------------------------------

def _infer_contract_type(file_name: str, content: str, category: str) -> str:
    type_map = {
        "bond":             "bond_tokenization",
        "equity":           "equity_token",
        "asset_transfer":   "asset_transfer",
        "escrow":           "escrow",
        "trade_settlement": "trade_settlement",
        "option":           "option_contract",
        "cash_payment":     "cash_payment",
        "nft":              "nft_ownership",
        "swap":             "swap",
        "lending":          "lending",
        "vote":             "governance_voting",
        "proposal":         "governance_proposal",
        "kyc":              "identity_kyc",
        "credential":       "identity_credential",
        "supply":           "supply_chain",
        "shipment":         "supply_chain_shipment",
        "invoice":          "invoice_payment",
        "wallet":           "wallet",
        "holding":          "token_holding",
        "transfer":         "token_transfer",
        "auction":          "auction",
        "marketplace":      "marketplace",
        "chess":            "gaming",
        "crowdfund":        "crowdfunding",
        "chat":             "messaging",
        "task":             "task_tracking",
        "ticket":           "ticketing",
        "approval":         "approval_chain",
    }
    fn_lower = file_name.lower()
    for key, contract_type in type_map.items():
        if key in fn_lower:
            return contract_type

    # Try content-based matching
    content_lower = content.lower()
    for key, contract_type in type_map.items():
        if key in content_lower:
            return contract_type

    # Use category as fallback
    if category != "utilities":
        return category
    return "generic"


# ---------------------------------------------------------------------------
# File-level metadata extraction
# ---------------------------------------------------------------------------

def _extract_file_metadata(content: str) -> dict:
    """Extract structural metadata for filtering and scoring."""
    lines = content.split("\n")
    line_count = len(lines)

    templates = re.findall(r"^template\s+(\w+)", content, re.MULTILINE)
    choices = re.findall(r"^\s+(?:nonconsuming\s+|preconsuming\s+|postconsuming\s+)?choice\s+(\w+)", content, re.MULTILINE)
    choices = list(dict.fromkeys(choices))
    has_interfaces = bool(re.search(r"\binterface\s+\w+", content, re.MULTILINE))

    if line_count > 150 or len(templates) > 3 or len(choices) > 6 or has_interfaces:
        complexity = "complex"
    elif line_count > 60 or len(templates) > 1 or len(choices) > 2:
        complexity = "medium"
    else:
        complexity = "simple"

    return {
        "template_count": len(templates),
        "choice_count": len(choices),
        "has_interfaces": has_interfaces,
        "complexity": complexity,
        "line_count": line_count,
        "templates": templates,
        "choices": choices,
    }


# ---------------------------------------------------------------------------
# Smart chunking — full_file, template, choice, signature, import
# ---------------------------------------------------------------------------

def _chunk_daml_file(content: str, file_name: str) -> list[dict]:
    """
    Produce multiple chunk types for tiered retrieval:
      - full_file:  entire file (for deep-context retrieval)
      - template:   individual template blocks
      - choice:     individual choice blocks
      - signature:  compact fingerprint (template name + with-block + signatory/observer)
      - imports:    import block (for dependency reference)
    """
    chunks: list[dict] = []

    # 1) Full file chunk
    chunks.append({"type": "full_file", "content": content})

    # 2) Import block chunk
    import_lines = [l for l in content.split("\n") if l.strip().startswith("import ")]
    if import_lines:
        chunks.append({"type": "imports", "content": "\n".join(import_lines)})

    # 3) Template chunks + 4) Choice chunks + 5) Signature chunks
    template_blocks = _extract_template_blocks(content)
    for tpl in template_blocks:
        # Full template chunk
        chunks.append({"type": "template", "content": tpl["content"]})

        # Signature chunk (compact: template name + with-block + signatory/observer only)
        sig = _build_signature(tpl)
        if sig:
            chunks.append({"type": "signature", "content": sig})

        # Per-choice chunks
        for choice in tpl.get("choices", []):
            chunks.append({"type": "choice", "content": choice["content"]})

    # Also extract interface blocks
    interface_blocks = _extract_interface_blocks(content)
    for iface in interface_blocks:
        chunks.append({"type": "interface", "content": iface["content"]})

    return chunks


def _extract_template_blocks(content: str) -> list[dict]:
    """Extract individual template blocks with their choices."""
    blocks: list[dict] = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect template start (must be at column 0 or after a blank line)
        if re.match(r"^template\s+\w+", line):
            tpl_name = stripped.replace("template ", "").strip()
            tpl_lines = [line]
            tpl_indent = len(line) - len(line.lstrip())
            i += 1

            # Collect all lines belonging to this template
            while i < len(lines):
                cur = lines[i]
                # Template ends when we hit another top-level definition
                if cur.strip() and not cur[0].isspace() and not cur.strip().startswith("--"):
                    break
                tpl_lines.append(cur)
                i += 1

            tpl_content = "\n".join(tpl_lines).rstrip()

            # Extract choices within this template
            choices = _extract_choices_from_block(tpl_content)

            # Extract with-block (fields)
            with_block = _extract_with_block(tpl_content)

            # Extract signatory/observer lines
            sig_line = ""
            obs_line = ""
            for tl in tpl_lines:
                if re.match(r"^\s+signatory\s+", tl):
                    sig_line = tl.strip()
                if re.match(r"^\s+observer\s+", tl):
                    obs_line = tl.strip()

            blocks.append({
                "name": tpl_name,
                "content": tpl_content,
                "choices": choices,
                "with_block": with_block,
                "signatory": sig_line,
                "observer": obs_line,
            })
        else:
            i += 1

    return blocks


def _extract_choices_from_block(template_content: str) -> list[dict]:
    """Extract individual choice blocks from a template block."""
    choices: list[dict] = []
    lines = template_content.split("\n")
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        # Match choice definitions (including nonconsuming/preconsuming variants)
        choice_match = re.match(
            r"^\s+(?:nonconsuming\s+|preconsuming\s+|postconsuming\s+)?choice\s+(\w+)",
            lines[i]
        )
        if choice_match:
            choice_name = choice_match.group(1)
            choice_indent = len(lines[i]) - len(lines[i].lstrip())
            choice_lines = [lines[i]]
            i += 1

            # Collect choice body
            while i < len(lines):
                cur = lines[i]
                cur_stripped = cur.strip()
                if not cur_stripped:
                    choice_lines.append(cur)
                    i += 1
                    continue
                cur_indent = len(cur) - len(cur.lstrip())
                # Choice ends when indent returns to template level or new choice/ensure/key
                if cur_indent <= choice_indent and cur_stripped and not cur_stripped.startswith("--"):
                    break
                choice_lines.append(cur)
                i += 1

            choices.append({
                "name": choice_name,
                "content": "\n".join(choice_lines).rstrip(),
            })
        else:
            i += 1

    return choices


def _extract_with_block(template_content: str) -> str:
    """Extract the with-block (field definitions) from a template."""
    lines = template_content.split("\n")
    with_lines: list[str] = []
    in_with = False

    for line in lines:
        stripped = line.strip()
        if stripped == "with":
            in_with = True
            with_lines.append(line)
            continue
        if in_with:
            if stripped.startswith("where") or stripped.startswith("deriving"):
                break
            if stripped and not stripped.startswith("--"):
                # Must look like a field definition (name : Type)
                if re.match(r"\w+\s*:", stripped):
                    with_lines.append(line)
                else:
                    break

    return "\n".join(with_lines)


def _build_signature(tpl: dict) -> str:
    """Build a compact pattern signature for fast matching."""
    parts = [f"template {tpl['name']}"]
    if tpl.get("with_block"):
        parts.append(tpl["with_block"])
    if tpl.get("signatory"):
        parts.append(f"  {tpl['signatory']}")
    if tpl.get("observer"):
        parts.append(f"  {tpl['observer']}")
    # Add just choice names (not full bodies)
    for ch in tpl.get("choices", []):
        parts.append(f"  choice {ch['name']}")

    sig = "\n".join(parts)
    # Only useful if it has real content beyond just the template name
    if len(sig.split("\n")) > 2:
        return sig
    return ""


def _extract_interface_blocks(content: str) -> list[dict]:
    """Extract interface definition blocks."""
    blocks: list[dict] = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        if re.match(r"^interface\s+\w+", lines[i]):
            iface_name = lines[i].strip().split()[1]
            iface_lines = [lines[i]]
            i += 1

            while i < len(lines):
                cur = lines[i]
                if cur.strip() and not cur[0].isspace() and not cur.strip().startswith("--"):
                    break
                iface_lines.append(cur)
                i += 1

            blocks.append({
                "name": iface_name,
                "content": "\n".join(iface_lines).rstrip(),
            })
        else:
            i += 1

    return blocks
