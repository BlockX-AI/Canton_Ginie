"""
Multi-template project writer agent.

When ``project_mode`` is True the pipeline routes here instead of the
single-template writer.  Generation happens in stages so each LLM call
has the previously generated code as context:

  Stage 1 — Shared types module  (data types, enums)
  Stage 2 — Core template         (main business object)
  Stage 3 — Supporting templates   (lifecycle, transfer, utility — one call each)

The ``daml.yaml`` is built deterministically (never by the LLM).
"""

from __future__ import annotations

import re
import structlog

from security.generation_rules import format_rules_for_prompt
from utils.llm_client import call_llm

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# SDK version — must match what `daml build` expects
# ---------------------------------------------------------------------------
_SDK_VERSION = "2.10.3"

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_TYPES_SYSTEM_PROMPT = """You are an expert Daml 2.x engineer.
Generate a DAML module that defines shared data types and enums.

RULES:
1. Module name MUST be: Types
2. Start with `module Types where`
3. Import DA.Time, DA.Date, DA.Text
4. Define ONLY data types and type synonyms — NO templates
5. Use 2-space indentation, no tabs
6. No markdown fences
7. Return ONLY raw Daml code starting with `module Types where`"""

_TEMPLATE_SYSTEM_PROMPT = """You are an expert Daml 2.x engineer for Canton Network smart contracts.
You produce COMPILABLE Daml code. Follow these rules EXACTLY:

MANDATORY STRUCTURE:
module {module_name} where

import DA.Time
import DA.Date
import DA.Text
{extra_imports}

template {template_name}
  with
    <fields>
  where
    signatory <party>
    observer <party>
    ensure <condition>
    choice <Name> : <ReturnType>
      with <params>
      controller <party>
      do <body>

ABSOLUTE RULES:
1. Module MUST be named exactly: {module_name}
2. ALWAYS import DA.Time, DA.Date, DA.Text — and ONLY these imports
3. NEVER import other generated modules (no `import Bond`, `import Types`, etc.)
4. Define exactly ONE template named {template_name}
5. Use Party for participant fields, Decimal for financial amounts
6. Every template MUST have signatory, observer, ensure, and at least one choice
7. Choice syntax: `choice Name : ReturnType` then `with` then `controller` then `do`
8. `with` params MUST come BEFORE `controller` in choices
9. Inside choices use field names directly — NEVER `this.fieldName`
10. Decimal is built-in — NEVER import DA.Decimal or DA.Numeric
11. 2-space indentation, no tabs, no commas in `with` blocks
12. No markdown fences, no explanation text
13. Do NOT generate any Script test functions
14. All data types must be defined INLINE — do not reference external types

OUTPUT: Return ONLY the raw Daml code starting with `module {module_name} where`. Nothing else."""

# Append security rules
_SECURITY_RULES_BLOCK = format_rules_for_prompt()


def run_project_writer_agent(
    structured_intent: dict,
    rag_context: list[str] | None = None,
) -> dict:
    """Multi-stage generation returning a dict of files + deterministic daml.yaml.

    Returns::

        {
            "success": True,
            "files": {"daml/Types.daml": "...", "daml/Bond.daml": "...", ...},
            "daml_yaml": "sdk-version: ...",
            "primary_template": "Bond",          # for deploy agent
        }
    """
    rag_context = rag_context or []
    intent = structured_intent
    parties = intent.get("parties", ["issuer", "investor"])
    templates_spec = intent.get("templates", [])
    templates_needed = intent.get("daml_templates_needed", ["Main"])
    features = intent.get("features", [])
    contract_type = intent.get("contract_type", "generic")
    description = intent.get("description", "")
    constraints = intent.get("business_constraints", [])

    # Derive template list from intent
    if templates_spec:
        core_templates = [t for t in templates_spec if t.get("role") == "core"]
        support_templates = [t for t in templates_spec if t.get("role") != "core"]
    else:
        # Build from daml_templates_needed
        core_templates = [{"name": templates_needed[0], "role": "core", "parties": parties}] if templates_needed else []
        support_templates = [{"name": n, "role": "lifecycle", "parties": parties} for n in templates_needed[1:]]

    if not core_templates:
        core_templates = [{"name": _derive_name(contract_type, description), "role": "core", "parties": parties}]

    primary_name = core_templates[0]["name"]
    project_name = _sanitize_project_name(primary_name)

    files: dict[str, str] = {}
    generated_context: list[str] = []  # accumulate for later stages

    # ------------------------------------------------------------------
    # Stage 1: Core template (self-contained, no cross-module imports)
    # ------------------------------------------------------------------
    core_spec = core_templates[0]
    core_module = core_spec["name"]
    core_code = _generate_template(
        module_name=core_module,
        template_name=core_spec["name"],
        parties=core_spec.get("parties", parties),
        features=features,
        description=description,
        constraints=constraints,
        extra_imports="",
        rag_context=rag_context,
        prior_context=[],
    )
    if not core_code:
        logger.error("Core template generation failed")
        return {"success": False, "error": "Core template generation failed"}

    files[f"daml/{core_module}.daml"] = core_code
    generated_context.append(core_code)

    # ------------------------------------------------------------------
    # Stage 2: Supporting templates (self-contained, no cross-module imports)
    # Each file is standalone — only uses DA.* stdlib imports.
    # Prior context is passed as reference for naming consistency.
    # ------------------------------------------------------------------
    for tspec in support_templates[:4]:  # cap at 4 supporting templates
        mod_name = tspec["name"]

        sup_code = _generate_template(
            module_name=mod_name,
            template_name=mod_name,
            parties=tspec.get("parties", parties),
            features=[],
            description=f"{mod_name} template for {description[:100]}",
            constraints=[],
            extra_imports="",
            rag_context=[],
            prior_context=generated_context,
            role=tspec.get("role", "lifecycle"),
        )
        if sup_code:
            files[f"daml/{mod_name}.daml"] = sup_code
            generated_context.append(sup_code)

    # ------------------------------------------------------------------
    # Build daml.yaml deterministically
    # ------------------------------------------------------------------
    daml_yaml = _build_daml_yaml(project_name)

    logger.info(
        "Project writer completed",
        file_count=len(files),
        files=list(files.keys()),
        primary_template=primary_name,
    )

    return {
        "success": True,
        "files": files,
        "daml_yaml": daml_yaml,
        "primary_template": primary_name,
    }


# ---------------------------------------------------------------------------
# Internal generation helpers
# ---------------------------------------------------------------------------

def _generate_types_module(
    contract_type: str,
    description: str,
    features: list[str],
) -> str | None:
    """Generate a small Types.daml module with shared data types."""
    features_str = ", ".join(features[:5]) if features else "basic"
    user_msg = f"""Generate shared data types for a {contract_type} project.
Description: {description[:200]}
Features: {features_str}

Generate 2-4 useful data types or enums (e.g. Status, Currency, etc.).
Keep it small — only types that will be reused across multiple templates.
Start with: module Types where"""

    try:
        raw = call_llm(
            system_prompt=_TYPES_SYSTEM_PROMPT,
            user_message=user_msg,
            max_tokens=1024,
        )
        code = _extract_daml(raw)
        if not code or "module Types where" not in code:
            return None
        return _clean_code(code)
    except Exception as e:
        logger.warning("Types module generation failed", error=str(e))
        return None


def _generate_template(
    module_name: str,
    template_name: str,
    parties: list[str],
    features: list[str],
    description: str,
    constraints: list[str],
    extra_imports: str,
    rag_context: list[str],
    prior_context: list[str],
    role: str = "core",
) -> str | None:
    """Generate a single DAML template file."""
    party1 = parties[0] if parties else "issuer"
    party2 = parties[1] if len(parties) > 1 else "investor"

    system_prompt = _TEMPLATE_SYSTEM_PROMPT.format(
        module_name=module_name,
        template_name=template_name,
        extra_imports=extra_imports,
    ) + _SECURITY_RULES_BLOCK

    # Build context section
    context_section = ""
    if prior_context:
        context_section = "\n\nPREVIOUSLY GENERATED CODE (for reference — import these modules, do NOT redefine their types):\n"
        for ctx in prior_context[-2:]:  # only last 2 to stay within context window
            context_section += f"\n--- Reference ---\n{ctx[:600]}\n"

    rag_section = ""
    if rag_context:
        rag_section = "\n\nWORKING DAML EXAMPLES:\n"
        for i, ex in enumerate(rag_context[:2], 1):
            rag_section += f"\n--- Example {i} ---\n{ex[:400]}\n"

    constraints_section = ""
    if constraints:
        constraints_section = "\nBUSINESS CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in constraints)

    role_guidance = ""
    if role == "lifecycle":
        role_guidance = f"\nThis is a LIFECYCLE template (e.g., coupon payment, redemption). It should reference the core template '{parties[0]}' and handle one specific business event."
    elif role == "transfer":
        role_guidance = "\nThis is a TRANSFER template. It should handle ownership transfer of the core asset."

    user_msg = f"""Generate a compilable Daml module for:

MODULE: {module_name}
TEMPLATE: {template_name}
ROLE: {role}
DESCRIPTION: {description[:200]}
{role_guidance}

PARTIES:
- {party1} : Party (signatory)
- {party2} : Party (observer)

FEATURES: {', '.join(features) if features else 'Standard ' + role + ' operations'}
{constraints_section}
{extra_imports and f'IMPORTS NEEDED: {extra_imports}'}
{context_section}
{rag_section}

IMPORTANT: Module must be '{module_name}', template must be '{template_name}'.
Use {party1} as signatory, {party2} as observer.
Start with: module {module_name} where"""

    for attempt in range(2):
        try:
            raw = call_llm(
                system_prompt=system_prompt,
                user_message=user_msg,
                max_tokens=4096,
            )
            code = _extract_daml(raw)
            if not code or len(code.strip()) < 30:
                continue
            code = _clean_code(code)
            # Ensure correct module name
            code = re.sub(
                r"^(\s*)module\s+\w+\s+where",
                f"\\1module {module_name} where",
                code,
                count=1,
                flags=re.MULTILINE,
            )
            return code
        except Exception as e:
            logger.warning("Template generation failed", template=template_name, attempt=attempt, error=str(e))

    logger.error("Template generation failed after retries", template=template_name)
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_daml_yaml(project_name: str) -> str:
    """Build daml.yaml deterministically — never via LLM."""
    safe = re.sub(r"[^a-z0-9-]", "-", project_name.lower())[:40]
    return f"""sdk-version: {_SDK_VERSION}
name: {safe}
version: 0.0.1
source: daml
dependencies:
  - daml-prim
  - daml-stdlib
"""


def _derive_name(contract_type: str, description: str) -> str:
    name = contract_type or (description.split()[0] if description else "Contract")
    name = re.sub(r"[^a-zA-Z0-9]", " ", name)
    parts = name.split()
    camel = "".join(w.capitalize() for w in parts if w)
    return camel[:30] if camel else "Contract"


def _sanitize_project_name(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", name.lower())[:40]


def _extract_daml(raw: str) -> str:
    fenced = re.search(r"```(?:daml|haskell)?\n(.*?)```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    if "module " in raw:
        idx = raw.index("module ")
        return raw[idx:].strip()
    return raw.strip()


def _clean_code(code: str) -> str:
    code = re.sub(r"```(?:daml|haskell)?\s*", "", code)
    code = code.replace("```", "")
    code = code.replace("\t", "  ")
    code = re.sub(r"(:\s*\w+)\s*,\s*$", r"\1", code, flags=re.MULTILINE)
    code = re.sub(r"\bthis\.([a-z][a-zA-Z0-9_]*)\b", r"\1", code)
    code = re.sub(r"^\s*import DA\.Decimal.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"^\s*import DA\.Numeric.*$", "", code, flags=re.MULTILINE)
    # Strip cross-module imports (anything that's not DA.* or Daml.*)
    code = re.sub(r"^\s*import\s+(?!DA\.|Daml\.)\w+.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r";\s*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"\n{4,}", "\n\n\n", code)
    return code.strip()
