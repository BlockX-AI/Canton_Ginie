import re
import structlog

from utils.llm_client import call_llm

logger = structlog.get_logger()

FIX_SYSTEM_PROMPT = """You are a Daml compiler error specialist for Canton Network contracts.
You receive broken Daml code and compiler error messages, then return a corrected version.

RULES:
1. Read the errors carefully
2. Fix ONLY the broken section(s)
3. Return the COMPLETE corrected Daml file
4. Preserve the original module name (it may NOT be Main in project mode)
5. Use 2-space indentation
6. No markdown fences in output
7. Start with `module <ModuleName> where`

COMMON FIXES:
- "No signatory" → Add `signatory <party>` in `where` block
- "parse error" → Check indentation, `with` vs `where` blocks
- "Variable not in scope" → Check `with` block fields, remove `this.` prefix
- "Could not find module" → Add import at top
- "Couldn't match type" → Use Party for parties, Decimal for numbers
- "Multiple declarations" → Remove duplicate template/choice
- "Multiple ensure" → Merge into ONE ensure with &&
- `with` params MUST come BEFORE `controller` in choices
- Decimal is built-in — never import DA.Decimal

OUTPUT: Return ONLY corrected Daml code. No explanation. Start with `module <ModuleName> where`."""

ERROR_EXPLANATIONS = {
    "missing_signatory":    "Add `signatory <partyField>` in the `where` block.",
    "type_mismatch":        "Use Party for parties, Decimal for numbers, Text for strings.",
    "parse_error":          "Check indentation (2 spaces), missing `do`, misplaced `with`.",
    "unknown_variable":     "Variable not defined in `with` block or missing import.",
    "missing_import":       "Add `import ModuleName` at the top.",
    "ambiguous_occurrence": "Qualify the name or rename to avoid conflict.",
    "multiple_declaration": "Remove the duplicate template or choice.",
    "ensure_error":         "Use ONE ensure clause, combine with &&.",
    "choice_error":         "`with` params before `controller`, then `do`.",
    "indentation_error":    "Use exactly 2 spaces per level, no tabs.",
    "unknown":              "Check the full error message.",
}


def run_fix_agent(daml_code: str, compile_errors: list[dict], attempt_number: int) -> dict:
    logger.info("Running fix agent", attempt=attempt_number, error_count=len(compile_errors))

    # First, try targeted fixes
    fixed_code = _apply_targeted_fixes(daml_code, compile_errors)
    if fixed_code != daml_code:
        logger.info("Targeted fixes applied", attempt=attempt_number, code_length=len(fixed_code))
        return {"success": True, "fixed_code": fixed_code}

    # Targeted fixes didn't help — use LLM
    logger.info("Targeted fixes made no change, using LLM fix", attempt=attempt_number)

    error_descriptions = _format_errors_for_llm(compile_errors)
    raw_stderr = compile_errors[0].get("raw", "") if compile_errors else ""

    if attempt_number >= 3:
        user_message = _build_regeneration_message(daml_code, error_descriptions)
    else:
        user_message = _build_fix_message(daml_code, error_descriptions, raw_stderr)

    try:
        raw = call_llm(
            system_prompt=FIX_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )
        if not raw or len(raw.strip()) < 30:
            logger.warning("Fix agent: LLM returned empty response")
            return {"success": True, "fixed_code": daml_code}

        clean_code = _extract_daml_code(raw)
        # Post-process LLM output
        clean_code = _sanitize_fix_output(clean_code)
        logger.info("Fix agent completed", attempt=attempt_number, code_length=len(clean_code))
        return {"success": True, "fixed_code": clean_code}
    except Exception as e:
        logger.error("Fix agent failed", error=str(e))
        return {"success": False, "error": str(e), "fixed_code": daml_code}


def _apply_targeted_fixes(code: str, errors: list[dict]) -> str:
    """Apply all targeted fixes synchronously. Returns modified code."""
    for error in errors[:10]:
        error_type = error.get("type", error.get("error_type", "unknown"))

        if error_type == "multiple_declaration":
            code = _fix_multiple_declaration_sync(code, error)
        elif error_type == "missing_signatory":
            code = _fix_missing_signatory_sync(code)
        elif error_type == "unknown_variable":
            code = _fix_unknown_variable_sync(code, error)
        elif error_type in ("missing_import", "import_error"):
            code = _fix_import_error_sync(code, error)
        elif error_type == "type_mismatch":
            code = _fix_type_mismatch_sync(code, error)
        elif error_type == "parse_error":
            code = _fix_parse_error_sync(code, error)
        elif error_type == "choice_error":
            code = _fix_choice_error_sync(code, error)
        elif error_type == "indentation_error":
            code = code.replace("\t", "  ")
        elif error_type == "ensure_error":
            code = _fix_ensure_error_sync(code)
        elif error_type == "ambiguous_occurrence":
            # Remove module-qualified field access
            code = re.sub(r'\b([A-Z][a-zA-Z0-9_]*)\.([a-z][a-zA-Z0-9_]*)\b', r'\2', code)

    return code


def _fix_multiple_declaration_sync(code: str, error: dict) -> str:
    """Remove duplicate template/choice definitions."""
    msg = error.get("message", "")
    dup_name_m = re.search(r"Multiple declarations of [\u2018\u2019'`\"](\w+)[\u2018\u2019'`\"]", msg)
    if not dup_name_m:
        dup_name_m = re.search(r"Multiple declarations of (\w+)", msg)
    if not dup_name_m:
        # Try removing duplicate templates by finding all template starts
        template_starts = list(re.finditer(r"^template\s+(\w+)", code, re.MULTILINE))
        if len(template_starts) > 1:
            # Keep only the first template
            code = code[:template_starts[1].start()].rstrip()
        return code

    name = dup_name_m.group(1)
    dup_line = error.get("line", 0)
    if dup_line <= 0:
        # Remove second occurrence of template/choice with that name
        pattern = re.compile(rf"^(\s*)(template|choice)\s+{re.escape(name)}\b", re.MULTILINE)
        matches = list(pattern.finditer(code))
        if len(matches) > 1:
            # Remove from second match to next same-indent block
            start = matches[1].start()
            lines = code[:start].rstrip() + "\n"
            rest = code[start:]
            # Find end of duplicate block
            rest_lines = rest.split("\n")
            indent = len(rest_lines[0]) - len(rest_lines[0].lstrip())
            end_idx = len(rest_lines)
            for k in range(1, len(rest_lines)):
                s = rest_lines[k].strip()
                if not s:
                    continue
                ci = len(rest_lines[k]) - len(rest_lines[k].lstrip())
                if ci <= indent and s:
                    end_idx = k
                    break
            code = lines + "\n".join(rest_lines[end_idx:])
        return code

    lines = code.split("\n")
    if dup_line > len(lines):
        return code

    idx = dup_line - 1
    block_start = idx
    for k in range(idx, -1, -1):
        stripped = lines[k].strip()
        if stripped.startswith(f"choice {name}") or stripped.startswith(f"template {name}"):
            block_start = k
            break

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


def _fix_missing_signatory_sync(code: str) -> str:
    """Add signatory if missing."""
    if re.search(r"^\s+signatory\s+", code, re.MULTILINE):
        return code
    party_field = re.search(r"^\s+(\w+)\s*:\s*Party", code, re.MULTILINE)
    party_name = party_field.group(1) if party_field else "issuer"
    # Insert after `where`
    code = re.sub(r"(  where\s*\n)", f"  where\n    signatory {party_name}\n", code, count=1)
    return code


def _fix_unknown_variable_sync(code: str, error: dict) -> str:
    """Fix this.field references and remove bad module qualifiers."""
    if "this." in code:
        code = re.sub(r"\bthis\.([a-z][a-zA-Z0-9_]*)\b", r"\1", code)
    # Remove module-qualified field access like TemplateName.field
    code = re.sub(r'\b([A-Z][a-zA-Z0-9]*)\.((?!Script|Date|Time|Text|Map|Set|List|Optional)[a-z][a-zA-Z0-9_]*)\b', r'\2', code)
    return code


_MISSING_IMPORTS = {
    "DA.Time":  ["Time", "RelTime", "addRelTime", "hours", "minutes", "seconds"],
    "DA.Date":  ["Date", "date", "fromGregorian", "toGregorian", "Month"],
    "DA.List":  ["sortOn", "dedup", "head", "tail"],
    "DA.Map":   ["Map", "fromList", "toList", "lookup"],
    "DA.Set":   ["Set", "member"],
    "DA.Text":  ["Text", "explode", "intercalate"],
}

_BAD_IMPORTS = [
    r'^\s*import DA\.Decimal.*$',
    r'^\s*import DA\.Numeric.*$',
]


def _fix_import_error_sync(code: str, error: dict) -> str:
    """Add missing imports and remove bad ones."""
    msg = error.get("message", "")

    # Remove bad imports
    for pat in _BAD_IMPORTS:
        code = re.sub(pat, "", code, flags=re.MULTILINE)

    # Detect needed import
    needed = None
    for module, keywords in _MISSING_IMPORTS.items():
        for kw in keywords:
            if kw in msg:
                needed = module
                break
        if needed:
            break

    if needed and f"import {needed}" not in code:
        lines = code.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("import "):
                insert_idx = i + 1
            elif line.startswith("module "):
                insert_idx = i + 1
        lines.insert(insert_idx, f"import {needed}")
        code = "\n".join(lines)

    return code


def _fix_type_mismatch_sync(code: str, error: dict) -> str:
    """Fix Int→Decimal, Numeric→Decimal, and Date/Time issues."""
    msg = error.get("message", "")
    line_idx = error.get("line", 0) - 1
    lines = code.split("\n")

    # Global: toGregorian → date
    if "toGregorian" in code and "Date" in msg:
        code = re.sub(r"\btime\s+\(toGregorian\s+(\w+)\)", r"time \1", code)
    if "(Int, Month, Int)" in msg or "Month" in msg:
        code = re.sub(r"toGregorian\s+", "", code)

    lines = code.split("\n")
    if 0 <= line_idx < len(lines):
        line = lines[line_idx]
        if ": Int" in line and "Int64" not in line:
            lines[line_idx] = line.replace(": Int", ": Decimal")
            return "\n".join(lines)
        if "Numeric" in line:
            lines[line_idx] = re.sub(r"Numeric\s+\d+", "Decimal", line)
            return "\n".join(lines)
        if ": Float" in line:
            lines[line_idx] = line.replace(": Float", ": Decimal")
            return "\n".join(lines)

    return "\n".join(lines) if lines else code


def _fix_parse_error_sync(code: str, error: dict) -> str:
    """Fix common parse errors from LLM output."""
    code = code.replace("\t", "  ")
    code = re.sub(r"^```(?:daml|haskell)?\s*$", "", code, flags=re.MULTILINE)
    code = code.replace("```", "")
    code = re.sub(r"(:\s*\w+)\s*,\s*$", r"\1", code, flags=re.MULTILINE)
    code = re.sub(r"\bwhere\s*\{", "where", code)
    code = re.sub(r"^\s*\}\s*$", "", code, flags=re.MULTILINE)
    code = re.sub(r";\s*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"^\s*deriving.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"(\w+)\s*::\s*(\w+)", r"\1 : \2", code)
    return code


def _fix_choice_error_sync(code: str, error: dict) -> str:
    """Fix choice ordering: with must come before controller."""
    controller_re = re.compile(r'^(\s*)controller\b(.*)$', re.MULTILINE)
    with_block_re = re.compile(r'^(\s*)with\s*$')

    lines = code.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        cm = controller_re.match(line)
        if cm:
            indent = cm.group(1)
            j = i + 1
            if j < len(lines) and with_block_re.match(lines[j]):
                with_lines = [lines[j]]
                j += 1
                while j < len(lines):
                    wl = lines[j]
                    if wl.strip() == '' or (wl.startswith(indent + '  ') and not wl.strip().startswith('do')):
                        with_lines.append(wl)
                        j += 1
                    else:
                        break
                result.extend(with_lines)
                result.append(line)
                i = j
                continue
        result.append(line)
        i += 1
    return "\n".join(result)


def _fix_ensure_error_sync(code: str) -> str:
    """Merge multiple ensure clauses into one."""
    lines = code.split("\n")
    result = []
    ensure_conditions = []
    ensure_indent = ""
    in_where = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("where"):
            in_where = True
            if ensure_conditions:
                # Flush previous
                merged = " && ".join(ensure_conditions)
                result.append(f"{ensure_indent}ensure {merged}")
                ensure_conditions = []
            result.append(line)
            continue

        if in_where and stripped.startswith("ensure "):
            ensure_indent = line[:len(line) - len(stripped)]
            cond = stripped[len("ensure "):].strip()
            ensure_conditions.append(cond)
            continue

        if ensure_conditions:
            merged = " && ".join(ensure_conditions)
            result.append(f"{ensure_indent}ensure {merged}")
            ensure_conditions = []

        if stripped.startswith("template "):
            in_where = False

        result.append(line)

    if ensure_conditions:
        merged = " && ".join(ensure_conditions)
        result.append(f"{ensure_indent}ensure {merged}")

    return "\n".join(result)


def _sanitize_fix_output(code: str) -> str:
    """Post-process LLM fix output."""
    code = re.sub(r"```(?:daml|haskell)?\s*", "", code)
    code = code.replace("```", "")
    code = code.replace("\t", "  ")
    code = re.sub(r'\bthis\.([a-z][a-zA-Z0-9_]*)\b', r'\1', code)
    code = re.sub(r'^\s*import DA\.Decimal.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*import DA\.Numeric.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r"(:\s*\w+)\s*,\s*$", r"\1", code, flags=re.MULTILINE)
    code = re.sub(r";\s*$", "", code, flags=re.MULTILINE)
    return code.strip()


def _format_errors_for_llm(errors: list[dict]) -> str:
    if not errors:
        return "No specific errors found."

    parts = []
    for i, err in enumerate(errors[:5], 1):
        error_type = err.get("type", err.get("error_type", "unknown"))
        explanation = ERROR_EXPLANATIONS.get(error_type, ERROR_EXPLANATIONS["unknown"])
        part = f"""Error {i}:
  Location: {err.get('file', 'Main.daml')} line {err.get('line', '?')}, column {err.get('column', '?')}
  Message: {err.get('message', 'Unknown error')}
  Type: {error_type}
  Fix hint: {explanation}"""
        parts.append(part)
    return "\n\n".join(parts)


def _build_fix_message(daml_code: str, error_descriptions: str, raw_stderr: str = "") -> str:
    raw_section = ""
    if raw_stderr:
        clean = _strip_sdk_banner(raw_stderr)
        raw_section = f"\nRAW COMPILER OUTPUT:\n{clean[:2000]}\n"

    return f"""Fix the following Daml code. It has compiler errors.

CURRENT DAML CODE:
{daml_code}

COMPILER ERRORS:
{error_descriptions}
{raw_section}
Return the complete corrected Daml file. Start with `module Main where`."""


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
    return f"""The Daml code below has persistent errors after multiple fix attempts.
Rewrite it completely from scratch, keeping the same business logic.

BROKEN CODE (reference only):
{daml_code}

ERRORS:
{error_descriptions}

Rewrite as a single module Main with one template, proper signatory/observer, ensure, and choices.
Start with `module Main where`."""


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
# Sandbox-based targeted fix agent (async)
# ---------------------------------------------------------------------------

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

    for error in compile_errors[:10]:
        error_type = error.get("type", "unknown")
        file_name = error.get("file", "Main.daml")
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
        fixed = _apply_targeted_fixes(code, [error])

        if fixed != original:
            await sandbox.files.write(file_path, fixed)
            changed = True
            logger.info("Applied targeted fix", error_type=error_type, file=file_name)

    return {
        "success": True,
        "changed": changed,
        "attempt": attempt + 1,
    }
