"""
generate_synthetic_patterns.py — Generate compilable DAML patterns via LLM
for categories underrepresented in the harvested corpus.

Usage:
    python -m scripts.generate_synthetic_patterns [--max-total 500] [--min-per-category 30]

Capped at 500 total synthetic patterns (quality over quantity).
Each generated pattern is compile-gate validated before saving.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Categories that are typically thin after repo harvesting
# ---------------------------------------------------------------------------

GAP_CATEGORIES: dict[str, list[dict]] = {
    "governance": [
        {"name": "SimpleVote", "desc": "Simple yes/no voting contract with quorum threshold"},
        {"name": "WeightedVote", "desc": "Weighted voting where vote power depends on token holdings"},
        {"name": "Proposal", "desc": "Proposal creation with voting period and execution"},
        {"name": "DaoTreasury", "desc": "DAO treasury with multi-sig spending approval"},
        {"name": "GovernanceToken", "desc": "Governance token with delegation and snapshot"},
        {"name": "Amendment", "desc": "Protocol amendment proposal with super-majority requirement"},
        {"name": "Council", "desc": "Council election and member management"},
        {"name": "Referendum", "desc": "Public referendum with time-locked execution"},
    ],
    "identity": [
        {"name": "KycVerification", "desc": "KYC verification with issuer attestation and expiry"},
        {"name": "CredentialIssuance", "desc": "Verifiable credential issuance and revocation"},
        {"name": "IdentityRegistry", "desc": "Identity registry with lookup and update"},
        {"name": "AccessControl", "desc": "Role-based access control with grant and revoke"},
        {"name": "AgeVerification", "desc": "Age verification without revealing birthdate"},
        {"name": "ComplianceAttestation", "desc": "Regulatory compliance attestation with audit trail"},
        {"name": "LicenseManagement", "desc": "Professional license issuance and renewal"},
    ],
    "supply_chain": [
        {"name": "ShipmentTracking", "desc": "Shipment tracking with location updates and delivery confirmation"},
        {"name": "WarehouseReceipt", "desc": "Warehouse receipt for stored goods with release authorization"},
        {"name": "QualityCertificate", "desc": "Quality inspection certificate with pass/fail and remediation"},
        {"name": "PurchaseOrder", "desc": "Purchase order with line items, approval, and fulfillment"},
        {"name": "BillOfLading", "desc": "Bill of lading for international shipping"},
        {"name": "ProvenanceRecord", "desc": "Product provenance tracking from origin to consumer"},
        {"name": "InventoryManagement", "desc": "Inventory management with stock in/out and reorder alerts"},
        {"name": "SupplierContract", "desc": "Long-term supplier agreement with SLA tracking"},
    ],
    "propose_accept": [
        {"name": "TradeProposal", "desc": "Bilateral trade proposal with accept/reject/counter"},
        {"name": "LoanRequest", "desc": "Loan request with terms, acceptance, and disbursement"},
        {"name": "ServiceAgreement", "desc": "Service agreement proposal with SLA terms"},
        {"name": "PartnershipProposal", "desc": "Partnership formation with multi-party acceptance"},
        {"name": "AssetSwapProposal", "desc": "Atomic asset swap proposal between two parties"},
        {"name": "InsuranceClaim", "desc": "Insurance claim submission with adjudication workflow"},
        {"name": "RentalAgreement", "desc": "Property rental agreement with deposit and termination"},
    ],
    "defi": [
        {"name": "LiquidityPool", "desc": "Liquidity pool with deposit, withdraw, and fee distribution"},
        {"name": "FlashLoan", "desc": "Flash loan with same-transaction repayment guarantee"},
        {"name": "YieldFarm", "desc": "Yield farming with staking, rewards, and unstaking"},
        {"name": "CollateralizedLoan", "desc": "Collateralized loan with liquidation threshold"},
        {"name": "OrderBook", "desc": "Limit order book with bid/ask matching"},
        {"name": "Staking", "desc": "Token staking with lock period and reward calculation"},
        {"name": "TokenVesting", "desc": "Token vesting schedule with cliff and linear unlock"},
    ],
    "utilities": [
        {"name": "Escrow", "desc": "Time-locked escrow with dispute resolution"},
        {"name": "MultiSig", "desc": "Multi-signature authorization requiring N-of-M approvals"},
        {"name": "TimeLock", "desc": "Time-locked contract that unlocks after a specified date"},
        {"name": "BatchProcessor", "desc": "Batch processing of multiple operations in one transaction"},
        {"name": "FeeCollector", "desc": "Fee collection with configurable rates and distribution"},
        {"name": "Notarization", "desc": "Document notarization with timestamp and hash verification"},
        {"name": "Subscription", "desc": "Recurring subscription with payment and cancellation"},
    ],
}

# ---------------------------------------------------------------------------
# LLM prompt for generating DAML patterns
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Daml 2.x engineer. Generate a complete, compilable Daml module.

RULES:
1. Start with: module Main where
2. Import DA.Time, DA.Date, DA.Text
3. Define exactly ONE template with the given name
4. Use Party for participant fields, Decimal for amounts, Text for strings
5. Every template MUST have signatory, observer, ensure, and at least 2 choices
6. Choice syntax: `choice Name : ReturnType` then `with` params then `controller` then `do`
7. `with` (parameters) MUST come BEFORE `controller` in choices
8. Use field names directly inside choices — NEVER `this.fieldName`
9. 2-space indentation, no tabs, no commas in `with` blocks
10. No markdown fences, no explanation text
11. No Script test functions
12. Decimal is built-in — do NOT import DA.Decimal or DA.Numeric
13. Include meaningful business logic in choices, not just trivial updates
14. Use `create this with field = value` to update fields
15. Use `archive self` or `return ()` for void choices

OUTPUT: Return ONLY raw Daml code starting with `module Main where`. Nothing else."""


def _build_generation_prompt(
    name: str,
    desc: str,
    category: str,
    few_shot_examples: list[str],
) -> str:
    """Build the user prompt for generating a synthetic pattern."""
    examples_section = ""
    if few_shot_examples:
        examples_section = "\n\nREFERENCE EXAMPLES (for style, not to copy):\n"
        for i, ex in enumerate(few_shot_examples[:2], 1):
            # Truncate long examples
            truncated = ex[:800] if len(ex) > 800 else ex
            examples_section += f"\n--- Example {i} ---\n{truncated}\n"

    return f"""Generate a complete Daml module for:

TEMPLATE NAME: {name}
CATEGORY: {category}
DESCRIPTION: {desc}

Requirements:
- Two Party fields (at minimum): one signatory, one observer
- At least one Decimal field if financial, or relevant data fields otherwise
- An ensure clause validating field constraints
- At least 2 meaningful choices with real business logic
- Follow all Daml 2.x syntax rules exactly
{examples_section}
Start your response with: module Main where"""


# ---------------------------------------------------------------------------
# Compilation validation (same as harvest_patterns.py)
# ---------------------------------------------------------------------------

def _validate_compiles(daml_content: str, daml_sdk_path: str, sdk_version: str) -> bool:
    """Compile a DAML pattern in isolation to verify it's valid."""
    with tempfile.TemporaryDirectory(prefix="daml_synth_") as tmpdir:
        daml_yaml = (
            f"sdk-version: {sdk_version}\n"
            "name: synth-pattern\n"
            "version: 0.0.1\n"
            "source: daml\n"
            "dependencies:\n"
            "  - daml-prim\n"
            "  - daml-stdlib\n"
        )
        Path(tmpdir, "daml.yaml").write_text(daml_yaml, encoding="utf-8")
        daml_dir = Path(tmpdir, "daml")
        daml_dir.mkdir()
        (daml_dir / "Main.daml").write_text(daml_content, encoding="utf-8")

        try:
            result = subprocess.run(
                [daml_sdk_path, "build", "--project-root", tmpdir],
                capture_output=True, text=True, timeout=60,
            )
            return result.returncode == 0
        except Exception:
            return False


def _extract_daml_code(raw: str) -> str:
    """Extract clean DAML code from LLM response."""
    # Strip markdown fences
    raw = re.sub(r"```(?:daml|haskell)?\s*", "", raw)
    raw = raw.replace("```", "")

    if "module Main where" in raw:
        idx = raw.index("module Main where")
        return raw[idx:].strip()
    return raw.strip()


# ---------------------------------------------------------------------------
# Main generation pipeline
# ---------------------------------------------------------------------------

def generate_synthetic_patterns(
    output_dir: str,
    daml_sdk_path: str,
    sdk_version: str = "2.10.3",
    max_total: int = 500,
    min_per_category: int = 30,
    existing_counts: dict[str, int] | None = None,
) -> dict:
    """
    Generate synthetic DAML patterns for underrepresented categories.

    Args:
        output_dir: Directory to save generated patterns
        daml_sdk_path: Path to daml CLI
        sdk_version: DAML SDK version
        max_total: Hard cap on total synthetic patterns
        min_per_category: Target minimum patterns per gap category
        existing_counts: Dict of {category: count} from harvest to determine gaps

    Returns:
        Summary stats dict
    """
    # Lazy import — only needed when actually generating
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.llm_client import call_llm

    if existing_counts is None:
        existing_counts = {}

    stats = {
        "generated": 0,
        "compiled": 0,
        "failed_compile": 0,
        "failed_llm": 0,
        "by_category": {},
    }

    total_generated = 0
    output_path = Path(output_dir)

    # Load existing patterns as few-shot examples
    few_shot_cache: dict[str, list[str]] = {}

    for category, specs in GAP_CATEGORIES.items():
        if total_generated >= max_total:
            break

        existing = existing_counts.get(category, 0)
        needed = max(0, min_per_category - existing)
        if needed == 0:
            logger.info("Category already has enough patterns", category=category, existing=existing)
            continue

        # Cap per-category generation
        to_generate = min(needed, len(specs), max_total - total_generated)
        logger.info("Generating synthetic patterns", category=category, count=to_generate, existing=existing)

        cat_dir = output_path / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        cat_generated = 0

        # Load a few existing patterns as examples
        few_shots = _load_few_shot_examples(output_path, category, few_shot_cache)

        for spec in specs[:to_generate]:
            if total_generated >= max_total:
                break

            prompt = _build_generation_prompt(
                name=spec["name"],
                desc=spec["desc"],
                category=category,
                few_shot_examples=few_shots,
            )

            # Try up to 2 times per pattern
            success = False
            for attempt in range(2):
                try:
                    raw = call_llm(
                        system_prompt=SYSTEM_PROMPT,
                        user_message=prompt,
                        max_tokens=2048,
                    )
                    if not raw or len(raw.strip()) < 50:
                        stats["failed_llm"] += 1
                        continue

                    code = _extract_daml_code(raw)

                    # Validate compilation
                    if _validate_compiles(code, daml_sdk_path, sdk_version):
                        file_name = f"synthetic__{spec['name']}.daml"
                        (cat_dir / file_name).write_text(code, encoding="utf-8")
                        stats["compiled"] += 1
                        cat_generated += 1
                        total_generated += 1
                        success = True
                        logger.info("Generated pattern", name=spec["name"], category=category)
                        break
                    else:
                        stats["failed_compile"] += 1
                        logger.debug("Pattern failed compilation", name=spec["name"], attempt=attempt)

                except Exception as e:
                    stats["failed_llm"] += 1
                    logger.warning("LLM call failed", name=spec["name"], error=str(e))

            stats["generated"] += 1

        stats["by_category"][category] = cat_generated
        logger.info("Category complete", category=category, generated=cat_generated)

    logger.info("Synthetic generation complete", **stats)
    return stats


def _load_few_shot_examples(
    output_path: Path,
    category: str,
    cache: dict[str, list[str]],
) -> list[str]:
    """Load up to 2 existing patterns from a category as few-shot examples."""
    if category in cache:
        return cache[category]

    examples: list[str] = []
    cat_dir = output_path / category
    if cat_dir.exists():
        for f in sorted(cat_dir.glob("*.daml"))[:2]:
            try:
                examples.append(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Fallback: use original examples
    if not examples:
        orig_dir = output_path / "original"
        if orig_dir.exists():
            for f in sorted(orig_dir.glob("*.daml"))[:2]:
                try:
                    examples.append(f.read_text(encoding="utf-8"))
                except Exception:
                    pass

    cache[category] = examples
    return examples


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic DAML patterns for gap categories")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent.parent / "rag" / "daml_examples"),
                        help="Output directory for patterns")
    parser.add_argument("--daml-sdk-path", default=None,
                        help="Path to daml CLI")
    parser.add_argument("--sdk-version", default="2.10.3")
    parser.add_argument("--max-total", type=int, default=500,
                        help="Maximum total synthetic patterns (hard cap)")
    parser.add_argument("--min-per-category", type=int, default=30,
                        help="Target minimum patterns per gap category")
    parser.add_argument("--harvest-manifest", default=None,
                        help="Path to harvest_manifest.json to read existing counts")

    args = parser.parse_args()

    # Resolve SDK path
    daml_sdk_path = args.daml_sdk_path
    if not daml_sdk_path:
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from config import get_settings
            daml_sdk_path = get_settings().daml_sdk_path
        except Exception:
            import shutil
            daml_sdk_path = shutil.which("daml") or "daml"

    # Load existing counts from harvest manifest
    existing_counts = {}
    manifest_path = args.harvest_manifest or os.path.join(args.output_dir, "harvest_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            existing_counts = manifest.get("stats", {}).get("by_category", {})
        logger.info("Loaded harvest manifest", counts=existing_counts)

    stats = generate_synthetic_patterns(
        output_dir=args.output_dir,
        daml_sdk_path=daml_sdk_path,
        sdk_version=args.sdk_version,
        max_total=args.max_total,
        min_per_category=args.min_per_category,
        existing_counts=existing_counts,
    )

    print("\n" + "=" * 50)
    print("SYNTHETIC GENERATION SUMMARY")
    print("=" * 50)
    print(f"  Attempts:        {stats['generated']}")
    print(f"  Compiled OK:     {stats['compiled']}")
    print(f"  Failed compile:  {stats['failed_compile']}")
    print(f"  Failed LLM:      {stats['failed_llm']}")
    print()
    print("  By category:")
    for cat, count in sorted(stats["by_category"].items()):
        print(f"    {cat:25s} {count}")
    print("=" * 50)


if __name__ == "__main__":
    main()
