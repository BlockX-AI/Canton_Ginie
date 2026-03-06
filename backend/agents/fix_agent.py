import re
import structlog
from anthropic import Anthropic

from config import get_settings

logger = structlog.get_logger()

FIX_SYSTEM_PROMPT = """You are a Daml compiler error specialist for Canton Network contracts.
You receive broken Daml code and compiler error messages, then return a corrected version.

YOUR TASK:
1. Read the Daml code carefully
2. Read the compiler error(s) carefully
3. Understand what the error means in Daml context
4. Fix ONLY the broken section(s) — do not rewrite unrelated parts
5. Return the COMPLETE corrected Daml file

COMMON DAML ERRORS AND FIXES:

Error: "No signatory" → Add `signatory <party>` inside the template's `where` block
Error: "parse error" → Check indentation (must be consistent 2-space), check `with` vs `where` blocks
Error: "Variable not in scope" → The variable/party is not defined in the `with` block
Error: "Could not find module" → Add the import at the top: `import ModuleName`
Error: "Couldn't match type" → Check you're using Party for parties, Decimal for numbers, Text for strings
Error: "controller ... not party" → The controller must reference a Party field from the template
Error: "Ambiguous occurrence" → Qualify the name or use a different identifier

DAML SYNTAX REMINDERS:
- `signatory` and `observer` must be directly inside `where` block (no indentation relative to where)
- Choice syntax: `choice Name : ReturnType\n  with\n    field : Type\n  controller party\n  do`
- `create this with field = value` for updating fields
- No trailing commas in `with` blocks
- `ContractId TemplateName` for contract references

OUTPUT: Return ONLY the complete corrected Daml code. No explanation. No markdown fences. Start with `module`."""

ERROR_EXPLANATIONS = {
    "missing_signatory":    "Every Daml template must have at least one signatory. Add `signatory <partyField>` in the `where` block.",
    "type_mismatch":        "There's a type mismatch. Check that Party fields use Party type, amounts use Decimal, and names use Text.",
    "parse_error":          "Daml syntax error. Common causes: wrong indentation, missing `do`, missing `where`, misplaced `with`.",
    "unknown_variable":     "A variable is used but not defined. Make sure all party and field names are declared in the `with` block.",
    "missing_import":       "A module is referenced but not imported. Add `import ModuleName` at the top of the file.",
    "ambiguous_occurrence": "An identifier matches multiple definitions. Qualify it with the module name (e.g., `Module.identifier`).",
    "wrong_controller":     "The controller expression is not a Party. Use a field name of type Party from the template's `with` block.",
    "indentation_error":    "Indentation must be consistent. Use exactly 2 spaces for each level.",
    "unknown":              "Check the full error message and ensure Daml syntax rules are followed.",
}


def run_fix_agent(daml_code: str, compile_errors: list[dict], attempt_number: int) -> str:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    logger.info("Running fix agent", attempt=attempt_number, error_count=len(compile_errors))

    error_descriptions = _format_errors_for_llm(compile_errors)
    needs_regeneration = _needs_full_regeneration(compile_errors)

    if needs_regeneration and attempt_number >= 2:
        user_message = _build_regeneration_message(daml_code, error_descriptions)
    else:
        user_message = _build_fix_message(daml_code, error_descriptions)

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        system=FIX_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    fixed_code = response.content[0].text.strip()
    clean_code = _extract_daml_code(fixed_code)

    logger.info("Fix agent completed", attempt=attempt_number, code_length=len(clean_code))
    return clean_code


def _format_errors_for_llm(errors: list[dict]) -> str:
    if not errors:
        return "No specific errors found. Try reviewing the overall structure."

    parts = []
    for i, err in enumerate(errors[:5], 1):
        error_type = err.get("error_type", "unknown")
        explanation = ERROR_EXPLANATIONS.get(error_type, ERROR_EXPLANATIONS["unknown"])

        part = f"""Error {i}:
  Location: {err.get('file', 'Main.daml')} line {err.get('line', '?')}, column {err.get('column', '?')}
  Message: {err.get('message', 'Unknown error')}
  Context: {err.get('context', '')}
  Type: {error_type}
  What it means: {explanation}"""
        parts.append(part)

    return "\n\n".join(parts)


def _build_fix_message(daml_code: str, error_descriptions: str) -> str:
    return f"""Fix the following Daml code. It has compiler errors that need to be resolved.

CURRENT DAML CODE:
{daml_code}

COMPILER ERRORS:
{error_descriptions}

Return the complete corrected Daml file. Fix only what is broken."""


def _build_regeneration_message(daml_code: str, error_descriptions: str) -> str:
    return f"""The following Daml code has structural errors that require a complete rewrite.
The errors indicate fundamental architectural issues.

ORIGINAL BROKEN CODE (for reference):
{daml_code}

ERRORS:
{error_descriptions}

Rewrite the complete Daml module from scratch, fixing all the architectural issues.
Keep the same business logic intent but fix the structure completely."""


def _needs_full_regeneration(errors: list[dict]) -> bool:
    architectural_types = {"missing_signatory", "wrong_controller"}
    for err in errors:
        if err.get("error_type") in architectural_types:
            return True
    return False


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
