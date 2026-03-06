import re
import structlog
from anthropic import Anthropic

from config import get_settings
from rag.vector_store import search_daml_patterns

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
10. ensure clauses validate pre-conditions
11. assertMsg for runtime checks inside choices
12. ContractId <TemplateName> is the type for contract references
13. Use `do` blocks for choice bodies
14. `create` creates a new contract, `archive` destroys one
15. `fetch` reads a contract without archiving it
16. `exercise` calls a choice on a contract

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


def run_writer_agent(structured_intent: dict, rag_context: list[str]) -> str:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

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

    logger.info("Running writer agent", contract_type=contract_type, templates=templates)

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        system=WRITER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    raw_code = response.content[0].text.strip()
    clean_code = _extract_daml_code(raw_code)

    logger.info("Writer agent completed", code_length=len(clean_code))
    return clean_code


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
