import re
import structlog

from config import get_settings
from rag.vector_store import search_daml_patterns
from utils.llm_client import call_llm

logger = structlog.get_logger()

WRITER_SYSTEM_PROMPT = """You are a senior Daml engineer specializing in Canton Network smart contracts.
You write production-ready Daml 2.x code that compiles without errors.

STRICT DAML SYNTAX RULES YOU MUST FOLLOW:
1. Always start with: module <ModuleName> where
2. Every template MUST have: signatory <party>
3. Every choice MUST have: controller <party>
4. Use Party type (not Text) for all party fields
5. Use Decimal (not Float) for all numeric financial values
6. All imports go at the top (import Daml.Script, etc.)
7. Indentation: use 2 spaces consistently
8. Template fields are separated by newlines, not commas
9. The `with` block for template fields uses no commas
10. CRITICAL: Each template can have AT MOST ONE `ensure` clause — combine multiple conditions with &&
    WRONG: ensure amount > 0.0 \n    ensure issuer /= investor
    RIGHT:  ensure amount > 0.0 && issuer /= investor
11. CRITICAL: NEVER use module-qualified names for template fields inside choice do-blocks
    WRONG: bond <- fetch CouponPayment.bondCid
    RIGHT:  bond <- fetch bondCid
12. assertMsg for runtime checks inside choices
13. ContractId <TemplateName> is the type for contract references
14. Use `do` blocks for choice bodies
15. `create` creates a new contract, `archive` destroys one
16. `fetch` reads a contract without archiving it
17. `exercise` calls a choice on a contract
18. CRITICAL: Every top-level Script function MUST have an explicit type annotation:
    WRONG: myTest = script do ...
    RIGHT:  myTest : Script ()
            myTest = script do ...
19. CRITICAL: Choice return type MUST match what the do-block actually returns:
    If return type is `ContractId Foo`, the last line must be `create Foo with ...`
    If return type is `()`, the last line must be `return ()` or `archive self`
    `archive self` returns `()`, not a ContractId
20. CRITICAL: `with` (parameters) MUST come BEFORE `controller` in choices:
    WRONG: choice Foo : ()\n  controller p\n  with\n    x : Int\n  do ...
    RIGHT:  choice Foo : ()\n  with\n    x : Int\n  controller p\n  do ...
21. CRITICAL: Inside choice do-blocks, use field names DIRECTLY — never `this.fieldName`:
    WRONG: assertMsg "" (this.borrower == p)
    RIGHT:  assertMsg "" (borrower == p)
22. CRITICAL: `Decimal` is built-in — NEVER write `import DA.Decimal` or `import DA.Numeric`
23. CRITICAL: In Daml.Script, exercise choices with: `submit party do exercise cid ChoiceName with ...`
    WRONG: exercise party cid ChoiceName
    RIGHT:  submit party do exercise cid ChoiceName

CANTON PARTY MODEL:
- Parties are named actors with permissions (NOT wallet addresses)
- signatory parties must sign for contract creation
- observer parties can see the contract
- controller inside a choice defines who can exercise it

VALID DAML TEMPLATE SKELETON:
```
template TemplateName
  with
    party1 : Party
    party2 : Party
    amount : Decimal
    description : Text
  where
    signatory party1
    observer  party2

    ensure amount > 0.0

    choice ChoiceName : ContractId TemplateName
      with newParty : Party
      controller party1
      do
        create this with party1 = newParty
```

OUTPUT FORMAT:
- Return ONLY the complete Daml code
- No markdown code fences
- No explanation text before or after
- Start directly with: module Main where"""


def run_writer_agent(structured_intent: dict, rag_context: list[str] = None) -> dict:
    settings = get_settings()

    parties = structured_intent.get("parties", ["owner", "counterparty"])
    features = structured_intent.get("features", [])
    templates = structured_intent.get("daml_templates_needed", ["Main"])
    contract_type = structured_intent.get("contract_type", "generic")
    constraints = structured_intent.get("business_constraints", [])
    choices = structured_intent.get("suggested_choices", [])
    description = structured_intent.get("description", "")

    rag_section = ""
    if rag_context:
        rag_section = "\n\nWORKING DAML EXAMPLES FOR REFERENCE:\n"
        for i, example in enumerate(rag_context[:3], 1):
            rag_section += f"\n--- Example {i} ---\n{example}\n"

    constraints_section = ""
    if constraints:
        constraints_section = "\nBUSINESS CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in constraints)

    user_message = f"""Generate a complete, compilable Daml module for the following contract:

CONTRACT TYPE: {contract_type}
DESCRIPTION: {description}

PARTIES:
{chr(10).join(f'- {p}' for p in parties)}

REQUIRED FEATURES:
{chr(10).join(f'- {f}' for f in features)}

TEMPLATES TO IMPLEMENT:
{chr(10).join(f'- {t}' for t in templates)}

CHOICES TO IMPLEMENT:
{chr(10).join(f'- {c}' for c in choices)}
{constraints_section}
{rag_section}

Write the complete Daml module. Use module name 'Main'. Include a setup script using Daml.Script for testing."""

    if rag_context is None:
        rag_context = []

    logger.info("Running writer agent", contract_type=contract_type, templates=templates)

    try:
        raw_code = call_llm(
            system_prompt=WRITER_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )
        
        if not raw_code:
            logger.error("Writer agent failed", error="LLM returned empty response")
            return {"success": False, "error": "LLM returned empty response", "daml_code": ""}
        
        clean_code = _extract_daml_code(raw_code)

        logger.info("Writer agent completed", code_length=len(clean_code))
        return {"success": True, "daml_code": clean_code}

    except Exception as e:
        logger.error("Writer agent failed", error=str(e))
        return {"success": False, "error": str(e), "daml_code": ""}


def fetch_rag_context(structured_intent: dict) -> list[str]:
    contract_type = structured_intent.get("contract_type", "")
    features = structured_intent.get("features", [])
    description = structured_intent.get("description", "")

    queries = [
        f"{contract_type} daml template canton",
        f"{' '.join(features[:3])} daml choice",
        description[:100],
    ]

    context_docs = []
    seen = set()

    for query in queries:
        try:
            results = search_daml_patterns(query, k=2)
            for doc in results:
                content = doc.page_content
                if content not in seen:
                    seen.add(content)
                    context_docs.append(content)
        except Exception as e:
            logger.warning("RAG search failed for query", query=query, error=str(e))

    return context_docs[:4]


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
