"""Curated pattern library loader.

We hand-author canonical Daml 2.x reference templates for common
contract patterns and store them in ``backend/rag/curated/<stem>.daml``.
The ``spec_synth`` stage tags each contract with a ``pattern`` (e.g.
``"voting-dao"``, ``"soulbound-credential"``); this module maps that
tag onto the matching ``.daml`` file and returns its raw source so the
writer agent can inject it into its few-shot prompt.

Failure mode: if no pattern matches (or the directory is missing),
``get_curated_example`` returns ``None`` and the writer falls back to
its existing vector-store RAG context. This module never raises.

Why a hand-curated library on top of the RAG vector store?
------------------------------------------------------------
The vector store retrieves anything semantically similar, including
LLM-generated examples that may themselves contain the bad habits we
want to discourage (numbered fields, duplicated per-party choices,
spurious ``amount : Decimal``). The curated examples are *audited*
\u2014 they are the ground truth for "good Daml 2.x for pattern X" and
they sit ABOVE the noisy RAG hits in the writer's prompt so the
imitation target is unambiguous.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

import structlog

logger = structlog.get_logger()

_CURATED_DIR = os.path.join(os.path.dirname(__file__), "curated")

# Aliases that map common spec.pattern / spec.domain values onto our
# canonical filename stems. Keys are matched case-insensitively as
# either exact or substring matches against the input.
_ALIASES: dict[str, str] = {
    # voting / governance
    "voting":               "voting-dao",
    "voting-dao":           "voting-dao",
    "dao":                  "voting-dao",
    "governance":           "voting-dao",
    "vote":                 "voting-dao",
    "ballot":               "voting-dao",
    "proposal":             "voting-dao",
    "election":             "voting-dao",
    # soulbound / credentials
    "soulbound":            "soulbound-credential",
    "soulbound-credential": "soulbound-credential",
    "credential":           "soulbound-credential",
    "badge":                "soulbound-credential",
    "certificate":          "soulbound-credential",
    "diploma":              "soulbound-credential",
    "membership":           "soulbound-credential",
    "attestation":          "soulbound-credential",
    "non-transferable":     "soulbound-credential",
    # escrow / payments
    "escrow":               "escrow",
    "hold":                 "escrow",
    "payments":             "escrow",
    # NFT / rights
    "nft":                  "nft",
    "collectible":          "nft",
    "rights":               "nft",
    "art":                  "nft",
    # bond / finance
    "bond":                 "bond-tokenization",
    "bond-tokenization":    "bond-tokenization",
    "note":                 "bond-tokenization",
    "fixed-income":         "bond-tokenization",
    "finance":              "bond-tokenization",
    # generic two-party agreement
    "propose-accept":       "propose-accept",
    "agreement":            "propose-accept",
    "contract":             "propose-accept",
    # invoice / billing lifecycle
    "invoice":              "invoice-processing",
    "invoice-processing":   "invoice-processing",
    "invoicing":            "invoice-processing",
    "billing":              "invoice-processing",
    "bill":                 "invoice-processing",
    "payment-request":      "invoice-processing",
    "accounts-receivable":  "invoice-processing",
    "ar":                   "invoice-processing",
}


@lru_cache(maxsize=1)
def _list_curated() -> frozenset[str]:
    """All available curated pattern stems (filenames sans extension)."""
    if not os.path.isdir(_CURATED_DIR):
        return frozenset()
    return frozenset(
        os.path.splitext(name)[0]
        for name in os.listdir(_CURATED_DIR)
        if name.endswith(".daml")
    )


@lru_cache(maxsize=32)
def _load_pattern(stem: str) -> Optional[str]:
    path = os.path.join(_CURATED_DIR, f"{stem}.daml")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _resolve_stem(query: Optional[str]) -> Optional[str]:
    """Map a free-form pattern / domain string to a curated file stem.

    Resolution priority:

    1. Exact alias hit (``"voting"`` -> ``"voting-dao"``).
    2. Exact filename hit (the query is already the canonical stem).
    3. Substring alias hit \u2014 longest matching alias key wins, so
       ``"soulbound-credential"`` beats a bare ``"credential"`` when
       both keys are substrings of the input.
    """
    if not query:
        return None
    needle = query.strip().lower()
    available = _list_curated()
    if not available:
        return None

    # 1. Exact alias
    target = _ALIASES.get(needle)
    if target and target in available:
        return target

    # 2. Already canonical stem
    if needle in available:
        return needle

    # 3. Substring match \u2014 prefer longest key
    matches = [
        (key, _ALIASES[key])
        for key in _ALIASES
        if key in needle and _ALIASES[key] in available
    ]
    if matches:
        matches.sort(key=lambda kv: -len(kv[0]))
        return matches[0][1]

    return None


def get_curated_example(
    pattern: Optional[str] = None,
    domain: Optional[str] = None,
) -> Optional[tuple[str, str]]:
    """Return ``(stem, source)`` for the best-matching curated pattern.

    ``pattern`` is checked first; ``domain`` is the fallback. Returns
    ``None`` if nothing matches \u2014 the writer should then proceed
    with its normal RAG context only.
    """
    stem = _resolve_stem(pattern) or _resolve_stem(domain)
    if not stem:
        return None
    src = _load_pattern(stem)
    if not src:
        return None
    logger.debug(
        "Curated pattern matched",
        query_pattern=pattern,
        query_domain=domain,
        resolved=stem,
    )
    return stem, src


def format_curated_for_prompt(
    pattern: Optional[str] = None,
    domain: Optional[str] = None,
) -> str:
    """Return a writer-ready prompt block, or ``""`` if no match.

    The block is wrapped in clear delimiters and sits in the prompt
    ABOVE the noisier vector-store RAG hits, so the writer treats it
    as the imitation target.
    """
    hit = get_curated_example(pattern, domain)
    if not hit:
        return ""
    stem, src = hit
    return (
        "\n--- GOLD-STANDARD REFERENCE FOR THIS PATTERN: "
        f"{stem} ---\n"
        "Treat this as the authoritative example of how to structure\n"
        "this kind of contract. IMITATE its structural choices:\n"
        "  * list-of-Party fields (e.g. `voters : [Party]`), NEVER\n"
        "    `voter1, voter2, voter3, voter4, voter5`.\n"
        "  * a SINGLE parameterised choice per behaviour (e.g. one\n"
        "    `CastVote` with `voter : Party` in the `with` block),\n"
        "    NEVER `VoteVoter1 .. VoteVoterN` clones.\n"
        "  * descriptive `assertMsg` strings for every invariant\n"
        "    (NOT bare `ensure` chains).\n"
        "  * deliberate OMISSION of choices that the pattern says\n"
        "    must not exist (e.g. no `Transfer` on a soulbound badge).\n"
        "Adapt field names and types to the user's specific request \u2014\n"
        "do NOT copy this file verbatim.\n\n"
        f"{src}\n"
        f"--- END GOLD-STANDARD REFERENCE ({stem}) ---\n"
    )
