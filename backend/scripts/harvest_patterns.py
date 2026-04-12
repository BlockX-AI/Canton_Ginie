"""
harvest_patterns.py — Clone official DAML repositories and extract compilable patterns.

Usage:
    python -m scripts.harvest_patterns [--skip-clone] [--skip-compile] [--max-patterns 2000]

Outputs organized .daml files into backend/rag/daml_examples/<category>/
Each file that passes the compile-gate is kept; failures go to quarantine/.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Repository definitions — prioritised by pattern density
# ---------------------------------------------------------------------------

REPOS = [
    # Tier 1: Must-have
    {
        "url": "https://github.com/digital-asset/daml.git",
        "name": "daml",
        "priority": 1,
        "mine_paths": ["sdk/", "templates/", "daml-lf/"],
        "shallow": True,
    },
    {
        "url": "https://github.com/digital-asset/canton.git",
        "name": "canton",
        "priority": 1,
        "mine_paths": ["community/", "examples/"],
        "shallow": True,
    },
    {
        "url": "https://github.com/digital-asset/daml-finance.git",
        "name": "daml-finance",
        "priority": 1,
        "mine_paths": ["src/"],
        "shallow": True,
    },
    {
        "url": "https://github.com/digital-asset/ex-models.git",
        "name": "ex-models",
        "priority": 1,
        "mine_paths": ["."],
        "shallow": True,
    },
    {
        "url": "https://github.com/digital-asset/cn-quickstart.git",
        "name": "cn-quickstart",
        "priority": 1,
        "mine_paths": ["quickstart/daml/", "daml/"],
        "shallow": True,
    },
    {
        "url": "https://github.com/hyperledger-labs/splice.git",
        "name": "splice",
        "priority": 1,
        "mine_paths": ["daml/", "token-standard/"],
        "shallow": True,
    },
    {
        "url": "https://github.com/digital-asset/daml-finance-app.git",
        "name": "daml-finance-app",
        "priority": 1,
        "mine_paths": ["src/daml/"],
        "shallow": True,
    },
    # Tier 2: High value
    {
        "url": "https://github.com/digital-asset/ex-secure-canton-infra.git",
        "name": "ex-secure-canton-infra",
        "priority": 2,
        "mine_paths": ["daml/"],
        "shallow": True,
    },
    {
        "url": "https://github.com/digital-asset/wallet-sample-app.git",
        "name": "wallet-sample-app",
        "priority": 2,
        "mine_paths": ["daml/"],
        "shallow": True,
    },
    {
        "url": "https://github.com/digital-asset/decentralized-canton-sync.git",
        "name": "decentralized-canton-sync",
        "priority": 2,
        "mine_paths": ["daml/"],
        "shallow": True,
    },
    # Tier 4: Community
    {
        "url": "https://github.com/ChainSafe/canton-erc20.git",
        "name": "canton-erc20",
        "priority": 4,
        "mine_paths": ["daml/"],
        "shallow": True,
    },
]

# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "defi":            ["swap", "amm", "lending", "borrow", "liquidity", "pool", "dex", "yield", "stake"],
    "securities":      ["bond", "equity", "option", "future", "derivative", "coupon", "maturity", "instrument"],
    "payments":        ["cash", "payment", "invoice", "remittance", "settlement", "transfer", "payout"],
    "supply_chain":    ["supply", "shipment", "logistics", "tracking", "provenance", "warehouse"],
    "governance":      ["vote", "voting", "proposal", "governance", "ballot", "quorum", "dao"],
    "identity":        ["kyc", "credential", "identity", "attestation", "verification"],
    "nft":             ["nft", "token", "collectible", "marketplace", "royalty", "mint"],
    "token_standards": ["cip56", "holding", "transferfactory", "transferinstruction", "amulet", "splice"],
    "daml_finance":    ["daml.finance", "instrument", "lifecycle", "claim", "holding", "account", "factory"],
    "interfaces":      ["interface", "implements", "viewtype", "requires"],
    "propose_accept":  ["propose", "accept", "approval", "workflow", "request", "confirm"],
    "testing":         ["script", "test", "scenario"],
    "utilities":       ["util", "helper", "lib", "common", "types", "data"],
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HarvestedPattern:
    content: str
    source_repo: str
    source_path: str
    module_name: str
    template_names: list[str] = field(default_factory=list)
    choice_names: list[str] = field(default_factory=list)
    party_fields: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    category: str = "utilities"
    complexity: str = "simple"    # simple | medium | complex
    has_interfaces: bool = False
    line_count: int = 0
    signature_hash: str = ""
    compile_passed: Optional[bool] = None


# ---------------------------------------------------------------------------
# Clone / pull repos
# ---------------------------------------------------------------------------

def clone_repos(clone_dir: str, repos: list[dict]) -> dict[str, str]:
    """Clone repos into clone_dir. Returns {repo_name: local_path}."""
    paths = {}
    clone_path = Path(clone_dir)
    clone_path.mkdir(parents=True, exist_ok=True)

    for repo in repos:
        name = repo["name"]
        dest = clone_path / name
        if dest.exists():
            logger.info("Repo already cloned, pulling latest", repo=name)
            try:
                subprocess.run(
                    ["git", "pull", "--ff-only"],
                    cwd=str(dest), capture_output=True, timeout=120,
                )
            except Exception as e:
                logger.warning("Git pull failed, using existing", repo=name, error=str(e))
            paths[name] = str(dest)
            continue

        logger.info("Cloning repo", repo=name, url=repo["url"])
        cmd = ["git", "clone"]
        if repo.get("shallow"):
            cmd += ["--depth", "1"]
        cmd += [repo["url"], str(dest)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                paths[name] = str(dest)
                logger.info("Cloned successfully", repo=name)
            else:
                logger.error("Clone failed", repo=name, stderr=result.stderr[:300])
        except subprocess.TimeoutExpired:
            logger.error("Clone timed out", repo=name)
        except FileNotFoundError:
            logger.error("git not found — install git and retry")
            sys.exit(1)

    return paths


# ---------------------------------------------------------------------------
# Find and extract .daml files
# ---------------------------------------------------------------------------

def find_daml_files(repo_path: str, mine_paths: list[str]) -> list[str]:
    """Find all .daml files under the specified sub-paths of a repo."""
    found = []
    repo = Path(repo_path)

    for sub in mine_paths:
        search_root = repo / sub.rstrip("/") if sub != "." else repo
        if not search_root.exists():
            continue
        for daml_file in search_root.rglob("*.daml"):
            # Skip hidden dirs, build artifacts, .daml cache
            parts = daml_file.relative_to(repo).parts
            if any(p.startswith(".") for p in parts):
                continue
            if any(p in ("dist", "build", "node_modules", "__pycache__") for p in parts):
                continue
            found.append(str(daml_file))

    return found


def extract_metadata(content: str) -> dict:
    """Extract structural metadata from DAML source."""
    lines = content.split("\n")
    line_count = len(lines)

    # Module name
    module_match = re.search(r"^module\s+([\w.]+)\s+where", content, re.MULTILINE)
    module_name = module_match.group(1) if module_match else "Unknown"

    # Template names
    templates = re.findall(r"^template\s+(\w+)", content, re.MULTILINE)

    # Choice names
    choices = re.findall(r"^\s+choice\s+(\w+)", content, re.MULTILINE)
    # Also nonconsuming/preconsuming choices
    choices += re.findall(r"^\s+(?:nonconsuming|preconsuming|postconsuming)\s+choice\s+(\w+)", content, re.MULTILINE)
    choices = list(dict.fromkeys(choices))  # deduplicate preserving order

    # Party fields
    party_fields = re.findall(r"(\w+)\s*:\s*Party", content)
    party_fields = list(dict.fromkeys(party_fields))

    # Imports
    imports = re.findall(r"^import\s+([\w.]+)", content, re.MULTILINE)

    # Has interfaces
    has_interfaces = bool(re.search(r"\binterface\s+\w+", content, re.MULTILINE))

    # Complexity scoring
    if line_count > 150 or len(templates) > 3 or len(choices) > 6 or has_interfaces:
        complexity = "complex"
    elif line_count > 60 or len(templates) > 1 or len(choices) > 2:
        complexity = "medium"
    else:
        complexity = "simple"

    return {
        "module_name": module_name,
        "template_names": templates,
        "choice_names": choices,
        "party_fields": party_fields,
        "imports": imports,
        "has_interfaces": has_interfaces,
        "complexity": complexity,
        "line_count": line_count,
    }


def classify_category(content: str, file_path: str, repo_name: str) -> str:
    """Classify a DAML file into a category based on content and path."""
    text = (content + " " + file_path).lower()

    # Special case: daml-finance repo
    if repo_name == "daml-finance":
        return "daml_finance"

    # Special case: splice/token standard
    if repo_name in ("splice", "canton-erc20"):
        return "token_standards"

    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)

    # Fallback: check path components
    path_lower = file_path.lower()
    if "test" in path_lower or "script" in path_lower:
        return "testing"
    if "example" in path_lower or "sample" in path_lower:
        return "utilities"

    return "utilities"


def compute_signature(content: str, templates: list[str], choices: list[str]) -> str:
    """Compute a dedup signature from template names + choice names + content hash."""
    sig_parts = sorted(templates) + sorted(choices)
    # Also include a truncated content hash to distinguish same-named but different templates
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    sig_string = "|".join(sig_parts) + "|" + content_hash
    return hashlib.md5(sig_string.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Quality filters
# ---------------------------------------------------------------------------

MIN_LINES = 10
MIN_TEMPLATE_KEYWORD = True  # Must contain "template" or "interface"


def passes_quality_filter(content: str, line_count: int) -> bool:
    """Quick quality check before attempting compilation."""
    if line_count < MIN_LINES:
        return False
    if MIN_TEMPLATE_KEYWORD and not re.search(r"\b(template|interface)\s+\w+", content):
        return False
    # Skip pure test/script files with no templates
    if re.search(r"^\w+\s*:\s*Script", content, re.MULTILINE) and not re.search(r"^template\s+", content, re.MULTILINE):
        return False
    return True


# ---------------------------------------------------------------------------
# Compile-gate validation
# ---------------------------------------------------------------------------

def validate_compiles(daml_content: str, daml_sdk_path: str, sdk_version: str = "2.10.3") -> bool:
    """Actually compile the pattern in an isolated temp project to verify validity."""
    with tempfile.TemporaryDirectory(prefix="daml_validate_") as tmpdir:
        # Write daml.yaml
        daml_yaml = (
            f"sdk-version: {sdk_version}\n"
            "name: validate-pattern\n"
            "version: 0.0.1\n"
            "source: daml\n"
            "dependencies:\n"
            "  - daml-prim\n"
            "  - daml-stdlib\n"
        )
        Path(tmpdir, "daml.yaml").write_text(daml_yaml, encoding="utf-8")

        # Write the .daml file
        daml_dir = Path(tmpdir, "daml")
        daml_dir.mkdir()

        # Use the module name from the content, or Main
        module_match = re.search(r"^module\s+([\w.]+)\s+where", daml_content, re.MULTILINE)
        if module_match:
            module_name = module_match.group(1)
            # Convert module path to file path (e.g., Daml.Finance.Asset -> Daml/Finance/Asset.daml)
            parts = module_name.split(".")
            file_path = daml_dir / "/".join(parts[:-1]) if len(parts) > 1 else daml_dir
            file_path.mkdir(parents=True, exist_ok=True)
            (file_path / f"{parts[-1]}.daml").write_text(daml_content, encoding="utf-8")
        else:
            (daml_dir / "Main.daml").write_text(daml_content, encoding="utf-8")

        # Try compilation
        try:
            result = subprocess.run(
                [daml_sdk_path, "build", "--project-root", tmpdir],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug("Compile validation failed", error=str(e))
            return False


# ---------------------------------------------------------------------------
# Main harvest pipeline
# ---------------------------------------------------------------------------

def harvest_from_repos(
    clone_dir: str,
    output_dir: str,
    daml_sdk_path: str,
    skip_clone: bool = False,
    skip_compile: bool = False,
    max_patterns: int = 2000,
    sdk_version: str = "2.10.3",
) -> dict:
    """
    Main entry point: clone repos, extract patterns, validate, organize.
    Returns a summary dict.
    """
    stats = {
        "repos_cloned": 0,
        "daml_files_found": 0,
        "passed_quality_filter": 0,
        "passed_compile_gate": 0,
        "duplicates_skipped": 0,
        "patterns_saved": 0,
        "by_category": {},
        "by_repo": {},
        "quarantined": 0,
    }

    # Step 1: Clone repos
    if skip_clone:
        repo_paths = {}
        for repo in REPOS:
            p = Path(clone_dir) / repo["name"]
            if p.exists():
                repo_paths[repo["name"]] = str(p)
    else:
        repo_paths = clone_repos(clone_dir, REPOS)

    stats["repos_cloned"] = len(repo_paths)

    # Step 2: Find all .daml files
    all_patterns: list[HarvestedPattern] = []
    seen_signatures: set[str] = set()

    for repo in REPOS:
        name = repo["name"]
        if name not in repo_paths:
            logger.warning("Repo not available, skipping", repo=name)
            continue

        daml_files = find_daml_files(repo_paths[name], repo["mine_paths"])
        logger.info("Found .daml files", repo=name, count=len(daml_files))
        stats["daml_files_found"] += len(daml_files)
        stats["by_repo"][name] = {"found": len(daml_files), "kept": 0}

        for file_path in daml_files:
            try:
                content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.debug("Cannot read file", path=file_path, error=str(e))
                continue

            meta = extract_metadata(content)

            # Quality filter
            if not passes_quality_filter(content, meta["line_count"]):
                continue
            stats["passed_quality_filter"] += 1

            # Dedup by signature
            sig = compute_signature(content, meta["template_names"], meta["choice_names"])
            if sig in seen_signatures:
                stats["duplicates_skipped"] += 1
                continue
            seen_signatures.add(sig)

            category = classify_category(content, file_path, name)

            pattern = HarvestedPattern(
                content=content,
                source_repo=name,
                source_path=str(Path(file_path).relative_to(repo_paths[name])),
                module_name=meta["module_name"],
                template_names=meta["template_names"],
                choice_names=meta["choice_names"],
                party_fields=meta["party_fields"],
                imports=meta["imports"],
                category=category,
                complexity=meta["complexity"],
                has_interfaces=meta["has_interfaces"],
                line_count=meta["line_count"],
                signature_hash=sig,
            )
            all_patterns.append(pattern)

    logger.info(
        "Extraction complete",
        total_candidates=len(all_patterns),
        quality_passed=stats["passed_quality_filter"],
        duplicates=stats["duplicates_skipped"],
    )

    # Step 3: Compile-gate (optional but recommended)
    if not skip_compile:
        logger.info("Running compile-gate validation (this may take a while)...")
        compiled_patterns = []
        quarantine_dir = Path(output_dir) / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        for i, pattern in enumerate(all_patterns):
            if i % 50 == 0:
                logger.info("Compile progress", current=i, total=len(all_patterns))

            passed = validate_compiles(pattern.content, daml_sdk_path, sdk_version)
            pattern.compile_passed = passed

            if passed:
                compiled_patterns.append(pattern)
                stats["passed_compile_gate"] += 1
            else:
                stats["quarantined"] += 1
                # Save to quarantine for manual review
                q_file = quarantine_dir / f"{pattern.source_repo}__{pattern.module_name}.daml"
                q_file.write_text(pattern.content, encoding="utf-8")

        all_patterns = compiled_patterns
        logger.info(
            "Compile-gate complete",
            passed=stats["passed_compile_gate"],
            quarantined=stats["quarantined"],
        )
    else:
        stats["passed_compile_gate"] = len(all_patterns)

    # Step 4: Enforce max_patterns limit (keep highest priority repos first)
    if len(all_patterns) > max_patterns:
        # Sort by priority (lower = better), then by complexity (complex first — more valuable)
        complexity_order = {"complex": 0, "medium": 1, "simple": 2}
        repo_priority = {r["name"]: r["priority"] for r in REPOS}
        all_patterns.sort(
            key=lambda p: (repo_priority.get(p.source_repo, 99), complexity_order.get(p.complexity, 2))
        )
        all_patterns = all_patterns[:max_patterns]

    # Step 5: Organize into category directories
    output_path = Path(output_dir)

    # Preserve original examples
    original_dir = output_path / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_path.glob("*.daml"):
        shutil.copy2(str(existing), str(original_dir / existing.name))

    # Create category directories and save patterns
    for pattern in all_patterns:
        cat_dir = output_path / pattern.category
        cat_dir.mkdir(parents=True, exist_ok=True)

        # Generate a clean filename
        safe_name = re.sub(r"[^\w]", "_", pattern.module_name)
        file_name = f"{pattern.source_repo}__{safe_name}.daml"
        target_file = cat_dir / file_name

        # Handle name collisions
        counter = 1
        while target_file.exists():
            file_name = f"{pattern.source_repo}__{safe_name}_{counter}.daml"
            target_file = cat_dir / file_name
            counter += 1

        target_file.write_text(pattern.content, encoding="utf-8")
        stats["patterns_saved"] += 1
        stats["by_category"][pattern.category] = stats["by_category"].get(pattern.category, 0) + 1
        stats["by_repo"][pattern.source_repo]["kept"] = stats["by_repo"].get(pattern.source_repo, {}).get("kept", 0) + 1

    # Step 6: Write manifest
    _non_word_re = re.compile(r"[^\w]")
    manifest = {
        "harvested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sdk_version": sdk_version,
        "stats": stats,
        "patterns": [
            {
                "file": f"{p.category}/{p.source_repo}__{_non_word_re.sub('_', p.module_name)}.daml",
                "repo": p.source_repo,
                "module": p.module_name,
                "templates": p.template_names,
                "choices": p.choice_names,
                "category": p.category,
                "complexity": p.complexity,
                "has_interfaces": p.has_interfaces,
                "line_count": p.line_count,
                "compile_passed": p.compile_passed,
            }
            for p in all_patterns
        ],
    }

    manifest_path = output_path / "harvest_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info("Harvest complete", **stats)
    return stats


# ---------------------------------------------------------------------------
# DAML SDK template extraction (intro1-9, skeleton, quickstart)
# ---------------------------------------------------------------------------

DAML_BUILTIN_TEMPLATES = [
    "daml-intro-1", "daml-intro-2", "daml-intro-3",
    "daml-intro-4", "daml-intro-5", "daml-intro-6",
    "daml-intro-7", "daml-intro-8", "daml-intro-9",
    "empty-skeleton",
]


def extract_sdk_templates(output_dir: str, daml_sdk_path: str) -> int:
    """Extract patterns from built-in daml new templates."""
    count = 0
    sdk_dir = Path(output_dir) / "sdk_templates"
    sdk_dir.mkdir(parents=True, exist_ok=True)

    for template in DAML_BUILTIN_TEMPLATES:
        with tempfile.TemporaryDirectory(prefix="daml_tpl_") as tmpdir:
            dest = Path(tmpdir) / template
            try:
                result = subprocess.run(
                    [daml_sdk_path, "new", str(dest), "--template", template],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode != 0:
                    logger.warning("daml new failed", template=template, stderr=result.stderr[:200])
                    continue

                # Find all .daml files in the generated project
                for daml_file in dest.rglob("*.daml"):
                    content = daml_file.read_text(encoding="utf-8")
                    if len(content.strip().split("\n")) >= MIN_LINES:
                        target = sdk_dir / f"{template}__{daml_file.stem}.daml"
                        target.write_text(content, encoding="utf-8")
                        count += 1

            except Exception as e:
                logger.warning("SDK template extraction failed", template=template, error=str(e))

    logger.info("SDK template extraction complete", count=count)
    return count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Harvest DAML patterns from official repositories")
    parser.add_argument("--clone-dir", default=str(Path(__file__).parent.parent.parent / "rag_repos"),
                        help="Directory to clone repos into")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent.parent / "rag" / "daml_examples"),
                        help="Output directory for organized patterns")
    parser.add_argument("--daml-sdk-path", default=None,
                        help="Path to daml CLI (default: from .env.ginie)")
    parser.add_argument("--sdk-version", default="2.10.3",
                        help="DAML SDK version for compile validation")
    parser.add_argument("--skip-clone", action="store_true",
                        help="Skip cloning, use existing repos")
    parser.add_argument("--skip-compile", action="store_true",
                        help="Skip compile-gate validation (faster but less reliable)")
    parser.add_argument("--max-patterns", type=int, default=2000,
                        help="Maximum number of patterns to keep")
    parser.add_argument("--extract-sdk-templates", action="store_true",
                        help="Also extract built-in daml new templates")

    args = parser.parse_args()

    # Resolve DAML SDK path
    daml_sdk_path = args.daml_sdk_path
    if not daml_sdk_path:
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from config import get_settings
            daml_sdk_path = get_settings().daml_sdk_path
        except Exception:
            daml_sdk_path = shutil.which("daml") or "daml"

    logger.info(
        "Starting pattern harvest",
        clone_dir=args.clone_dir,
        output_dir=args.output_dir,
        daml_sdk=daml_sdk_path,
        skip_clone=args.skip_clone,
        skip_compile=args.skip_compile,
        max_patterns=args.max_patterns,
    )

    stats = harvest_from_repos(
        clone_dir=args.clone_dir,
        output_dir=args.output_dir,
        daml_sdk_path=daml_sdk_path,
        skip_clone=args.skip_clone,
        skip_compile=args.skip_compile,
        max_patterns=args.max_patterns,
        sdk_version=args.sdk_version,
    )

    if args.extract_sdk_templates:
        sdk_count = extract_sdk_templates(args.output_dir, daml_sdk_path)
        stats["sdk_templates_extracted"] = sdk_count

    print("\n" + "=" * 60)
    print("HARVEST SUMMARY")
    print("=" * 60)
    print(f"  Repos cloned:          {stats['repos_cloned']}")
    print(f"  .daml files found:     {stats['daml_files_found']}")
    print(f"  Passed quality filter: {stats['passed_quality_filter']}")
    print(f"  Passed compile-gate:   {stats['passed_compile_gate']}")
    print(f"  Duplicates skipped:    {stats['duplicates_skipped']}")
    print(f"  Quarantined:           {stats['quarantined']}")
    print(f"  Patterns saved:        {stats['patterns_saved']}")
    print()
    print("  By category:")
    for cat, count in sorted(stats["by_category"].items()):
        print(f"    {cat:25s} {count}")
    print()
    print("  By repo:")
    for repo, info in sorted(stats["by_repo"].items()):
        print(f"    {repo:35s} found={info['found']:>4}  kept={info['kept']:>4}")
    print("=" * 60)


if __name__ == "__main__":
    main()
