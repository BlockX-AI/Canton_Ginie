import re
from typing import Optional


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")

_ERROR_PATTERNS: list[tuple[str, str]] = [
    ("multiple_declaration", r"Multiple declarations of|already defined|duplicate"),
    ("type_mismatch",        r"Couldn't match (expected )?type|type mismatch|Couldn't match"),
    ("missing_signatory",    r"No signatory|missing signatory|no signatories"),
    ("parse_error",          r"[Pp]arse error|lexical error|unexpected token"),
    ("unknown_variable",     r"Variable not in scope|Not in scope|not in scope"),
    ("import_error",         r"Could not find module|Module.*not found|Failed to load interface"),
    ("indentation_error",    r"[Ii]ndentation|dedent|unexpected indent"),
    ("choice_error",         r"choice.*not found|Invalid choice|unexpected.*choice"),
    ("ensure_error",         r"[Ee]nsure.*failed|Predicate failed|ensure"),
]

_FILE_LINE_PATTERN = re.compile(
    r"^([A-Za-z0-9_./-]+\.daml):(\d+):(\d+):\s*(?:error:\s*)?(.*)"
)

_STRUCTURED_RANGE = re.compile(r"^Range:\s+(\d+):(\d+)")
_STRUCTURED_FILE  = re.compile(r"^File:\s+(\S+)")
_STRUCTURED_MSG   = re.compile(r"^Message:")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


class ErrorClassifier:
    def parse_compile_output(self, stderr: str) -> list[dict]:
        clean = _strip_ansi(stderr)
        errors: list[dict] = []

        # --- Pass 1: structured DAML 2.x blocks (File: / Range: / Message:) ---
        lines = clean.splitlines()
        n = len(lines)
        i = 0
        while i < n:
            file_m = _STRUCTURED_FILE.match(lines[i].strip())
            if file_m:
                file_name = file_m.group(1)
                line_num = col_num = 0
                msg_lines: list[str] = []
                j = i + 1
                while j < n:
                    stripped = lines[j].strip()
                    range_m = _STRUCTURED_RANGE.match(stripped)
                    if range_m:
                        line_num = int(range_m.group(1))
                        col_num  = int(range_m.group(2))
                    elif _STRUCTURED_MSG.match(stripped):
                        k = j + 1
                        while k < n and lines[k].strip() and not _STRUCTURED_FILE.match(lines[k].strip()):
                            msg_lines.append(lines[k].strip())
                            k += 1
                        j = k
                        break
                    elif _STRUCTURED_FILE.match(stripped):
                        break
                    j += 1

                full_msg = " ".join(msg_lines).strip()
                # The actual file:line: error line is embedded inside msg_lines after ANSI strip
                for ml in msg_lines:
                    fm = _FILE_LINE_PATTERN.match(ml)
                    if fm:
                        file_name = fm.group(1)
                        line_num  = int(fm.group(2))
                        col_num   = int(fm.group(3))
                        full_msg  = fm.group(4).strip() + " " + " ".join(
                            ml2 for ml2 in msg_lines if ml2 != ml
                        )
                        break

                if full_msg:
                    errors.append({
                        "file":    file_name,
                        "line":    line_num,
                        "column":  col_num,
                        "type":    self._classify(full_msg),
                        "message": full_msg[:300],
                        "context": [],
                    })
                i = j
                continue
            i += 1

        # --- Pass 2: classic file:line:col: error lines ---
        if not errors:
            i = 0
            while i < n:
                match = _FILE_LINE_PATTERN.match(lines[i].strip())
                if match:
                    file_name = match.group(1)
                    line_num  = int(match.group(2))
                    col_num   = int(match.group(3))
                    first_msg = match.group(4).strip()

                    context_lines: list[str] = []
                    j = i + 1
                    while j < n and j < i + 6:
                        if _FILE_LINE_PATTERN.match(lines[j].strip()):
                            break
                        s = lines[j].strip()
                        if s:
                            context_lines.append(s)
                        j += 1

                    full_message = first_msg
                    if context_lines:
                        full_message = first_msg + " " + " ".join(context_lines)

                    errors.append({
                        "file":    file_name,
                        "line":    line_num,
                        "column":  col_num,
                        "type":    self._classify(full_message),
                        "message": first_msg,
                        "context": context_lines,
                    })
                    i = j
                else:
                    i += 1

        # --- Fallback: whole stderr as single unknown error ---
        if not errors and clean.strip():
            errors.append({
                "file":    "Main.daml",
                "line":    0,
                "column":  0,
                "type":    "unknown",
                "message": clean.strip()[:500],
                "context": [],
            })

        return errors

    def _classify(self, message: str) -> str:
        for error_type, pattern in _ERROR_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return error_type
        return "unknown"

    def suggest_fix(self, error: dict) -> str:
        suggestions = {
            "type_mismatch":     "Check field types. Use Decimal for numbers, Party for parties.",
            "missing_signatory": "Add 'signatory <party_field>' immediately after the 'where' clause.",
            "parse_error":       "Check syntax: indentation, missing commas, or mismatched brackets.",
            "unknown_variable":  "Import the required module or verify the variable name spelling.",
            "import_error":      "Add the missing import at the top of the file, e.g. 'import DA.Time'.",
            "indentation_error": "DAML uses 2-space indentation. Replace tabs with spaces.",
            "choice_error":      "Verify choice syntax: controller must appear before do.",
            "ensure_error":      "Ensure clause must evaluate to Bool. Check the condition expression.",
            "unknown":           "Review the full compiler message and DAML documentation.",
        }
        return suggestions.get(error.get("type", "unknown"), suggestions["unknown"])
