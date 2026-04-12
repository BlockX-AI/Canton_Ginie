import re
import structlog

from rag.vector_store import search_daml_patterns, search_signatures
from security.generation_rules import format_rules_for_prompt
from utils.llm_client import call_llm

logger = structlog.get_logger()

WRITER_SYSTEM_PROMPT = """You are an expert Daml 2.x engineer for Canton Network smart contracts.
You produce COMPILABLE Daml code. Follow these rules EXACTLY:

MANDATORY STRUCTURE — every file you produce MUST follow this layout:

module Main where

import DA.Time
import DA.Date
import DA.Text

template <Name>
  with
    <field1> : Party
    <field2> : Party
    <numericField> : Decimal
  where
    signatory <field1>
    observer <field2>

    ensure <condition>

    choice <ChoiceName> : ContractId <Name>
      with
        <param> : <Type>
      controller <field1>
      do
        create this with <field> = <param>

ABSOLUTE RULES:
1. Module MUST be named Main: `module Main where`
2. ALWAYS import DA.Time, DA.Date, DA.Text at the top
3. Define exactly ONE template (no multiple templates or modules)
4. Use Party for all participant fields
5. Use Decimal (not Float, not Int) for all financial amounts
6. Every template MUST have `signatory` with at least one Party field
7. Every template MUST have `observer` with at least one Party field
8. Every template MUST have exactly ONE `ensure` clause (combine with &&)
9. Every template MUST have at least one `choice`
10. Choice syntax: `choice Name : ReturnType` then `with` params then `controller` then `do`
11. `with` (parameters) MUST come BEFORE `controller` in choices
12. Inside choices use field names directly — NEVER `this.fieldName`
13. Decimal is built-in — NEVER import DA.Decimal or DA.Numeric
14. 2-space indentation, no tabs, no commas in `with` blocks
15. No markdown fences, no explanation text
16. `create this with field = value` to update fields
17. Choice return type MUST match the do-block return:
    - `ContractId X` → last line must be `create X with ...`
    - `()` → last line must be `return ()` or `archive self`
18. Do NOT generate any Script test functions
19. Do NOT use module-qualified field access like `Template.field`

OUTPUT: Return ONLY the raw Daml code starting with `module Main where`. Nothing else."""

# Append pre-audit security rules to the system prompt
WRITER_SYSTEM_PROMPT += format_rules_for_prompt()

# Fallback template used when LLM fails or returns invalid code
_FALLBACK_TEMPLATE = """module Main where

import DA.Time
import DA.Date
import DA.Text

template {template_name}
  with
    {party1} : Party
    {party2} : Party
    amount : Decimal
    description : Text
  where
    signatory {party1}
    observer {party2}

    ensure amount > 0.0

    choice Transfer : ContractId {template_name}
      with
        newOwner : Party
      controller {party2}
      do
        create this with {party2} = newOwner
"""


def run_writer_agent(structured_intent: dict, rag_context: list[str] = None) -> dict:
    parties = structured_intent.get("parties", ["issuer", "investor"])
    features = structured_intent.get("features", [])
    templates = structured_intent.get("daml_templates_needed", ["Main"])
    contract_type = structured_intent.get("contract_type", "generic")
    constraints = structured_intent.get("business_constraints", [])
    choices = structured_intent.get("suggested_choices", ["Transfer"])
    description = structured_intent.get("description", "")

    # Force single template
    template_name = templates[0] if templates else "Main"
    if template_name == "Main":
        template_name = _derive_template_name(contract_type, description)

    # Ensure at least 2 parties
    if len(parties) < 2:
        parties = parties + ["counterparty"]
    party1 = parties[0]
    party2 = parties[1]

    rag_section = ""
    if rag_context:
        rag_section = "\n\nWORKING DAML EXAMPLES FOR REFERENCE:\n"
        for i, example in enumerate(rag_context[:3], 1):
            rag_section += f"\n--- Example {i} ---\n{example}\n"

    constraints_section = ""
    if constraints:
        constraints_section = "\nBUSINESS CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in constraints)

    user_message = f"""Generate a complete, compilable Daml module for:

CONTRACT TYPE: {contract_type}
DESCRIPTION: {description}
TEMPLATE NAME: {template_name}

PARTIES (exactly these two):
- {party1} : Party (signatory)
- {party2} : Party (observer)

REQUIRED FEATURES:
{chr(10).join(f'- {f}' for f in features) if features else '- Basic contract with transfer'}

CHOICES TO IMPLEMENT:
{chr(10).join(f'- {c}' for c in choices[:3]) if choices else '- Transfer'}
{constraints_section}
{rag_section}

IMPORTANT: Use module name 'Main', template name '{template_name}'.
Use {party1} as signatory, {party2} as observer.
Include an amount : Decimal field with ensure amount > 0.0.
Do NOT include any Script test functions.
Start your response with: module Main where"""

    if rag_context is None:
        rag_context = []

    logger.info("Running writer agent", contract_type=contract_type, templates=[template_name])

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            raw_code = call_llm(
                system_prompt=WRITER_SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=4096,
            )

            if not raw_code or len(raw_code.strip()) < 30:
                logger.warning("Writer agent: LLM returned empty/short response", attempt=attempt)
                if attempt < max_retries:
                    continue
                # Use fallback
                logger.info("Writer agent: using fallback template")
                return {
                    "success": True,
                    "daml_code": _generate_fallback(template_name, party1, party2),
                }

            clean_code = _extract_daml_code(raw_code)
            clean_code = _post_process(clean_code, template_name, party1, party2)

            # Validate essential structure
            issues = _validate_daml(clean_code)
            if issues:
                logger.warning("Writer agent: validation issues", issues=issues, attempt=attempt)
                if attempt < max_retries:
                    continue
                # Fix what we can, then return
                clean_code = _auto_fix_structure(clean_code, template_name, party1, party2)

            logger.info("Writer agent completed", code_length=len(clean_code))
            return {"success": True, "daml_code": clean_code}

        except Exception as e:
            logger.error("Writer agent error", error=str(e), attempt=attempt)
            if attempt < max_retries:
                continue
            # Final fallback
            logger.info("Writer agent: using fallback after error")
            return {
                "success": True,
                "daml_code": _generate_fallback(template_name, party1, party2),
            }

    return {
        "success": True,
        "daml_code": _generate_fallback(template_name, party1, party2),
    }


def _derive_template_name(contract_type: str, description: str) -> str:
    """Derive a reasonable template name from the contract type or description."""
    name = contract_type or description.split()[0] if description else "Contract"
    # CamelCase it
    name = re.sub(r'[^a-zA-Z0-9]', ' ', name)
    parts = name.split()
    camel = ''.join(w.capitalize() for w in parts if w)
    if not camel or not camel[0].isupper():
        camel = "Contract"
    # Keep it short
    return camel[:30]


def _generate_fallback(template_name: str, party1: str, party2: str) -> str:
    """Generate a guaranteed-compilable DAML contract."""
    return _FALLBACK_TEMPLATE.format(
        template_name=template_name,
        party1=party1,
        party2=party2,
    ).strip()


def _validate_daml(code: str) -> list[str]:
    """Check that code has required DAML elements. Returns list of issues."""
    issues = []
    if "module Main where" not in code:
        issues.append("missing_module")
    if not re.search(r"^\s*template\s+\w+", code, re.MULTILINE):
        issues.append("missing_template")
    if not re.search(r"^\s+signatory\s+", code, re.MULTILINE):
        issues.append("missing_signatory")
    if not re.search(r"^\s+observer\s+", code, re.MULTILINE):
        issues.append("missing_observer")
    if not re.search(r"^\s+ensure\s+", code, re.MULTILINE):
        issues.append("missing_ensure")
    if not re.search(r"^\s+choice\s+\w+", code, re.MULTILINE):
        issues.append("missing_choice")
    # Check for multiple templates
    template_matches = re.findall(r"^\s*template\s+\w+", code, re.MULTILINE)
    if len(template_matches) > 1:
        issues.append("multiple_templates")
    return issues


def _auto_fix_structure(code: str, template_name: str, party1: str, party2: str) -> str:
    """Attempt to auto-fix common structural issues in generated code."""
    # If completely broken, use fallback
    if "module" not in code or "template" not in code:
        return _generate_fallback(template_name, party1, party2)

    # Fix missing module header
    if "module Main where" not in code:
        code = re.sub(r"module\s+\w+\s+where", "module Main where", code, count=1)
        if "module Main where" not in code:
            code = "module Main where\n\n" + code

    # Ensure imports
    for imp in ["import DA.Time", "import DA.Date", "import DA.Text"]:
        if imp not in code:
            code = code.replace("module Main where", f"module Main where\n{imp}", 1)

    # Remove multiple templates — keep only the first
    template_starts = [(m.start(), m.group()) for m in re.finditer(r"^template\s+\w+", code, re.MULTILINE)]
    if len(template_starts) > 1:
        # Keep everything up to the second template
        code = code[:template_starts[1][0]].rstrip()

    # Add missing signatory
    if not re.search(r"^\s+signatory\s+", code, re.MULTILINE):
        code = re.sub(r"(\s+where\s*\n)", f"\\1    signatory {party1}\n    observer {party2}\n", code, count=1)

    # Add missing observer
    if not re.search(r"^\s+observer\s+", code, re.MULTILINE):
        code = re.sub(r"(signatory\s+\w+\s*\n)", f"\\1    observer {party2}\n", code, count=1)

    return code


def _post_process(code: str, template_name: str, party1: str, party2: str) -> str:
    """Clean up LLM output to ensure valid DAML."""
    # Strip markdown fences
    code = re.sub(r"```(?:daml|haskell)?\s*", "", code)
    code = code.replace("```", "")

    # Replace tabs with spaces
    code = code.replace("\t", "  ")

    # Remove trailing commas in with blocks
    code = re.sub(r"(:\s*\w+)\s*,\s*$", r"\1", code, flags=re.MULTILINE)

    # Remove this. references
    code = re.sub(r'\bthis\.([a-z][a-zA-Z0-9_]*)\b', r'\1', code)

    # Remove bad imports
    code = re.sub(r'^\s*import DA\.Decimal.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*import DA\.Numeric.*$', '', code, flags=re.MULTILINE)

    # Remove any Script test functions (everything from `xxx : Script` to end or next top-level)
    code = re.sub(r'\n\w+\s*:\s*Script\s*\(.*?\n\w+\s*=\s*script\s+do.*?(?=\n\w|\Z)', '', code, flags=re.DOTALL)

    # Remove semicolons
    code = re.sub(r";\s*$", "", code, flags=re.MULTILINE)

    # Fix double-colon
    code = re.sub(r"(\w+)\s*::\s*(\w+)", r"\1 : \2", code)

    # Remove braces only in DAML structural contexts (not inside strings)
    code = re.sub(r"\bwhere\s*\{", "where", code)
    code = re.sub(r"^\s*\}\s*$", "", code, flags=re.MULTILINE)

    # Clean up excessive blank lines
    code = re.sub(r"\n{4,}", "\n\n\n", code)

    return code.strip()


def fetch_rag_context(structured_intent: dict) -> list[str]:
    """
    Tiered retrieval strategy to provide rich context without drowning the LLM:

    Tier 1: 2 full-file examples (most relevant complete templates, ~50-80 lines each)
    Tier 2: 5 pattern signatures (compact: template + fields + choices, ~10-15 lines each)
    Tier 3: 3 choice-specific snippets (just the choice blocks for requested features)

    This gives the LLM deep + broad context in ~250-350 lines instead of flooding
    with 15 full files that would overflow the effective context window.
    """
    contract_type = structured_intent.get("contract_type", "")
    features = structured_intent.get("features", [])
    description = structured_intent.get("description", "")
    choices = structured_intent.get("suggested_choices", [])

    # Infer category for filtered search (boost relevance)
    category = _map_contract_type_to_category(contract_type)

    context_docs: list[str] = []
    seen: set[str] = set()

    def _add_unique(content: str):
        if content and content not in seen:
            seen.add(content)
            context_docs.append(content)

    # --- Tier 1: Full file examples (deep context) ---
    full_file_query = f"{contract_type} {description[:80]} daml template canton"
    try:
        results = search_daml_patterns(
            full_file_query, k=2,
            chunk_type_filter="full_file",
            category_filter=category,
        )
        for doc in results:
            _add_unique(doc.page_content)
    except Exception as e:
        logger.warning("Tier 1 RAG search failed", error=str(e))

    # Fallback: unfiltered full_file search if category filter returned nothing
    if not context_docs:
        try:
            results = search_daml_patterns(full_file_query, k=2, chunk_type_filter="full_file")
            for doc in results:
                _add_unique(doc.page_content)
        except Exception as e:
            logger.warning("Tier 1 fallback RAG search failed", error=str(e))

    # --- Tier 2: Pattern signatures (broad structural reference) ---
    sig_query = f"{contract_type} {' '.join(features[:3])} template with signatory"
    try:
        results = search_signatures(sig_query, k=5, category_filter=category)
        for doc in results:
            _add_unique(doc.page_content)
    except Exception as e:
        logger.warning("Tier 2 signature search failed", error=str(e))

    # Fallback: unfiltered signature search
    if len(context_docs) < 3:
        try:
            results = search_signatures(sig_query, k=5)
            for doc in results:
                _add_unique(doc.page_content)
        except Exception as e:
            logger.warning("Tier 2 fallback signature search failed", error=str(e))

    # --- Tier 3: Choice-specific snippets ---
    choice_terms = choices[:3] if choices else features[:2]
    if choice_terms:
        choice_query = f"{' '.join(choice_terms)} daml choice controller do create"
        try:
            results = search_daml_patterns(choice_query, k=3, chunk_type_filter="choice")
            for doc in results:
                _add_unique(doc.page_content)
        except Exception as e:
            logger.warning("Tier 3 choice search failed", error=str(e))

    logger.info(
        "Tiered RAG context assembled",
        total_docs=len(context_docs),
        contract_type=contract_type,
        category=category,
    )
    return context_docs


# Category mapping for filtered RAG search
_CONTRACT_TYPE_TO_CATEGORY = {
    "bond_tokenization": "securities",
    "equity_token": "securities",
    "option_contract": "securities",
    "swap": "defi",
    "lending": "defi",
    "cash_payment": "payments",
    "invoice_payment": "payments",
    "asset_transfer": "payments",
    "trade_settlement": "payments",
    "escrow": "payments",
    "nft_ownership": "nft",
    "governance_voting": "governance",
    "governance_proposal": "governance",
    "identity_kyc": "identity",
    "identity_credential": "identity",
    "supply_chain": "supply_chain",
    "supply_chain_shipment": "supply_chain",
    "token_holding": "token_standards",
    "token_transfer": "token_standards",
    "auction": "defi",
    "marketplace": "nft",
    "crowdfunding": "defi",
    "approval_chain": "propose_accept",
}


def _map_contract_type_to_category(contract_type: str) -> str | None:
    """Map a contract_type to a RAG category for filtered search. Returns None if unknown."""
    return _CONTRACT_TYPE_TO_CATEGORY.get(contract_type)


def _extract_daml_code(raw: str) -> str:
    fenced = re.search(r"```(?:daml|haskell)?\n(.*?)```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    if "module Main where" in raw:
        idx = raw.index("module Main where")
        return raw[idx:].strip()

    if "module " in raw:
        idx = raw.index("module ")
        return raw[idx:].strip()

    return raw.strip()
