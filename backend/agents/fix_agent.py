import re
import structlog

from config import get_settings
from utils.llm_client import call_llm

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
Error: "Multiple 'ensure' declarations" → A template can only have ONE ensure clause. Merge conditions: `ensure cond1 && cond2`
Error: "parse error on input 'with'" → The `with` parameter block MUST come BEFORE `controller` in a choice definition
Error: "Couldn't match type 'Scenario' with 'Script'" → Add `: Script ()` type annotation before the script function, e.g. `myFn : Script ()` on the line before `myFn = script do`
Error: "Variable not in scope: this.fieldName" → Inside choices, use `fieldName` directly (no `this.` prefix)
Error: "Could not find module 'DA.Decimal'" → Remove the import; Decimal is built-in in Daml, no import needed

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
    "multiple_ensure":      "Each template can have at most ONE `ensure` clause. Merge all conditions: `ensure cond1 && cond2 && cond3`.",
    "choice_order":          "`with` (parameters) MUST come BEFORE `controller` in a choice. Move the `with` block above `controller`.",
    "scenario_not_script":   "Add `: Script ()` type annotation on the line BEFORE the `= script do` assignment.",
    "wrong_controller":     "The controller expression is not a Party. Use a field name of type Party from the template's `with` block.",
    "indentation_error":    "Indentation must be consistent. Use exactly 2 spaces for each level.",
    "unknown":              "Check the full error message and ensure Daml syntax rules are followed.",
}


def run_fix_agent(daml_code: str, compile_errors: list[dict], attempt_number: int) -> dict:
    logger.info("Running fix agent", attempt=attempt_number, error_count=len(compile_errors))

    error_descriptions = _format_errors_for_llm(compile_errors)
    needs_regeneration = _needs_full_regeneration(compile_errors)

    raw_stderr = compile_errors[0].get("raw", "") if compile_errors else ""

    if needs_regeneration and attempt_number >= 2:
        user_message = _build_regeneration_message(daml_code, error_descriptions)
    else:
        user_message = _build_fix_message(daml_code, error_descriptions, raw_stderr)

    try:
        raw = call_llm(
            system_prompt=FIX_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )
        clean_code = _extract_daml_code(raw)
        logger.info("Fix agent completed", attempt=attempt_number, code_length=len(clean_code))
        return {"success": True, "fixed_code": clean_code}
    except Exception as e:
        logger.error("Fix agent failed", error=str(e))
        return {"success": False, "error": str(e), "fixed_code": daml_code}


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


def _build_fix_message(daml_code: str, error_descriptions: str, raw_stderr: str = "") -> str:
    raw_section = ""
    if raw_stderr:
        clean = _strip_sdk_banner(raw_stderr)
        raw_section = f"\nRAW COMPILER OUTPUT (exact errors):\n{clean[:2000]}\n"

    return f"""Fix the following Daml code. It has compiler errors that need to be resolved.

CURRENT DAML CODE:
{daml_code}

COMPILER ERRORS (parsed):
{error_descriptions}
{raw_section}
Return the complete corrected Daml file. Fix only what is broken. Start with `module`."""


def _strip_sdk_banner(text: str) -> str:
    lines = text.split("\n")
    result = []
    skip = True
    for line in lines:
        if skip and ("SDK" in line or "github.com" in line or "Running single" in line
                     or "[INFO]" in line or "Compiling" in line or line.strip() == ""):
            continue
        skip = False
        result.append(line)
    return "\n".join(result) if result else text


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


# ---------------------------------------------------------------------------
# Sandbox-based targeted fix agent
# ---------------------------------------------------------------------------

_MISSING_IMPORTS = {
    "DA.Time":  ["Time", "datetime", "RelTime", "addRelTime"],
    "DA.Date":  ["Date", "date", "fromGregorian", "toGregorian"],
    "DA.List":  ["sortOn", "dedup", "head", "tail", "isPrefixOf"],
    "DA.Map":   ["Map", "fromList", "toList", "lookup", "insert", "delete"],
    "DA.Set":   ["Set", "fromList", "toList", "member", "insert", "delete"],
    "DA.Text":  ["Text", "explode", "intercalate", "isPrefixOf"],
}


def _detect_needed_import(message: str) -> str | None:
    for module, keywords in _MISSING_IMPORTS.items():
        for kw in keywords:
            if kw in message:
                return module
    return None


async def _fix_type_mismatch(code: str, error: dict) -> str:
    msg = error.get("message", "")

    # Fix: time (toGregorian date) h m s  →  time date h m s
    # toGregorian returns (Int,Month,Int) but time expects Date
    if "toGregorian" in code and "Date" in msg:
        fixed = re.sub(r"\btime\s+\(toGregorian\s+(\w+)\)", r"time \1", code)
        if fixed != code:
            return fixed

    # Fix: (Int, Month, Int) used where Date expected — drop toGregorian calls wholesale
    if "(Int, Month, Int)" in msg or "Month" in msg:
        fixed = re.sub(r"toGregorian\s+", "", code)
        if fixed != code:
            return fixed

    line_idx = error.get("line", 0) - 1
    lines = code.split("\n")
    if line_idx < 0 or line_idx >= len(lines):
        return code

    line = lines[line_idx]

    # Int → Decimal for numeric fields
    if "Int" in msg or ": Int" in line:
        lines[line_idx] = line.replace(": Int", ": Decimal")
        return "\n".join(lines)

    # Numeric n → Decimal
    if "Numeric" in line:
        lines[line_idx] = re.sub(r"Numeric\s+\d+", "Decimal", line)
        return "\n".join(lines)

    # Fix: fromGregorian (Int,Int,Int) → date
    if "fromGregorian" in line:
        lines[line_idx] = re.sub(r"fromGregorian\s+\d+\s+\w+\s+\d+", "(date 2024 Jan 1)", line)
        return "\n".join(lines)

    return code


async def _fix_missing_signatory(code: str) -> str:
    where_pattern = re.compile(r"(  where\n)(?!\s+signatory)")
    if where_pattern.search(code):
        # Find first Party field to use as signatory
        party_field_match = re.search(r"^\s+(\w+)\s*:\s*Party", code, re.MULTILINE)
        party_field = party_field_match.group(1) if party_field_match else "issuer"
        return where_pattern.sub(f"  where\n    signatory {party_field}\n", code, count=1)
    return code


async def _fix_import_error(code: str, error: dict) -> str:
    needed = _detect_needed_import(error.get("message", ""))
    if not needed:
        return code

    import_line = f"import {needed}"
    if import_line in code:
        return code

    lines = code.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import "):
            insert_idx = i + 1
        elif line.startswith("module "):
            insert_idx = i + 1

    lines.insert(insert_idx, import_line)
    return "\n".join(lines)


async def _fix_unknown_variable(code: str, error: dict) -> str:
    msg = error.get("message", "")
    # Strip "this." references — common mistake
    if "this." in code:
        return re.sub(r"\bthis\.([a-z][a-zA-Z0-9_]*)\b", r"\1", code)
    return code


async def _fix_parse_error(code: str, error: dict) -> str:
    """Fix common DAML parse errors produced by LLMs."""
    original = code

    # 1. Replace tabs with 2 spaces
    code = code.replace("\t", "  ")

    # 2. Remove markdown code fences the LLM may have left
    code = re.sub(r"^```(?:daml|haskell)?\s*$", "", code, flags=re.MULTILINE)

    # 3. Remove commas between template `with` fields
    #    e.g.  issuer : Party,  →  issuer : Party
    code = re.sub(r"(:\s*\w+)\s*,\s*$", r"\1", code, flags=re.MULTILINE)

    # 4. Remove braces that some LLMs add around template/choice bodies
    code = code.replace("{", "").replace("}", "")

    # 5. Fix `where {` → `where`
    code = re.sub(r"\bwhere\s*\{", "where", code)

    # 6. Remove semicolons
    code = re.sub(r";\s*$", "", code, flags=re.MULTILINE)

    # 7. Fix `deriving` lines (not valid in DAML)
    code = re.sub(r"^\s*deriving.*$", "", code, flags=re.MULTILINE)

    # 8. Fix double-colon type annotations `field :: Type` → `field : Type`
    code = re.sub(r"(\w+)\s*::\s*(\w+)", r"\1 : \2", code)

    if code != original:
        return code
    return original


async def _fix_multiple_declaration(code: str, error: dict) -> str:
    """
    Remove the SECOND definition of a duplicate choice/template name.
    The error message contains the name: 'Multiple declarations of Foo'
    and the duplicate line number.
    """
    msg = error.get("message", "")
    dup_name_m = re.search(r"Multiple declarations of [\u2018\u2019'`\"](\w+)[\u2018\u2019'`\"]", msg)
    if not dup_name_m:
        dup_name_m = re.search(r"Multiple declarations of (\w+)", msg)
    if not dup_name_m:
        return code

    name = dup_name_m.group(1)
    dup_line = error.get("line", 0)  # second (duplicate) declaration line
    if dup_line <= 0:
        return code

    lines = code.split("\n")
    if dup_line > len(lines):
        return code

    idx = dup_line - 1  # 0-based
    # Find the start of the block containing this duplicate (look backwards for choice/template)
    block_start = idx
    for k in range(idx, -1, -1):
        stripped = lines[k].strip()
        if stripped.startswith(f"choice {name}") or stripped.startswith(f"template {name}"):
            block_start = k
            break

    # Find end of the block (next same-level keyword or end of file)
    indent = len(lines[block_start]) - len(lines[block_start].lstrip())
    block_end = len(lines)
    for k in range(block_start + 1, len(lines)):
        stripped = lines[k].strip()
        if not stripped:
            continue
        cur_indent = len(lines[k]) - len(lines[k].lstrip())
        if cur_indent <= indent and stripped and not stripped.startswith("--"):
            block_end = k
            break

    del lines[block_start:block_end]
    return "\n".join(lines)


async def run_fix_agent_sandbox(
    sandbox,
    compile_errors: list[dict],
    attempt: int = 0,
    max_attempts: int = 5,
) -> dict:
    if attempt >= max_attempts:
        return {"success": False, "error": "Max fix attempts reached", "attempt": attempt}

    logger.info("Running sandbox fix agent", attempt=attempt, error_count=len(compile_errors))

    changed = False

    for error in compile_errors:
        error_type = error.get("type", "unknown")
        file_name = error.get("file", "Main.daml")
        # Normalise: strip any leading daml/ so we don't build daml/daml/...
        clean_name = file_name.lstrip("/").lstrip("\\")
        if clean_name.startswith("daml/") or clean_name.startswith("daml\\"):
            file_path = clean_name.replace("\\", "/")
        else:
            file_path = f"daml/{clean_name}"

        try:
            code = await sandbox.files.read(file_path)
        except FileNotFoundError:
            logger.warning("Fix agent: file not found", path=file_path)
            continue

        original = code

        if error_type == "type_mismatch":
            code = await _fix_type_mismatch(code, error)
        elif error_type == "missing_signatory":
            code = await _fix_missing_signatory(code)
        elif error_type == "import_error":
            code = await _fix_import_error(code, error)
        elif error_type == "unknown_variable":
            code = await _fix_unknown_variable(code, error)
        elif error_type == "indentation_error":
            code = code.replace("\t", "  ")
        elif error_type == "multiple_declaration":
            code = await _fix_multiple_declaration(code, error)
        elif error_type == "parse_error":
            code = await _fix_parse_error(code, error)
        else:
            logger.debug("No targeted fix for error type", error_type=error_type)
            continue

        if code != original:
            await sandbox.files.write(file_path, code)
            changed = True
            logger.info("Applied targeted fix", error_type=error_type, file=file_name)

    return {
        "success": True,
        "changed": changed,
        "attempt": attempt + 1,
    }
