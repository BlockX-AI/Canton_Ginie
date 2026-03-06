import os
import re
import uuid
import subprocess
import structlog
from pathlib import Path

from config import get_settings

logger = structlog.get_logger()

DAML_YAML_TEMPLATE = """sdk-version: 2.9.4
name: {project_name}
version: 0.0.1
source: daml
dependencies:
  - daml-prim
  - daml-stdlib
  - daml-script
"""

ERROR_PATTERNS = {
    "missing_signatory":    r"No signatory",
    "type_mismatch":        r"Couldn't match type|type mismatch",
    "parse_error":          r"parse error|Parse error",
    "unknown_variable":     r"Variable not in scope|Not in scope",
    "missing_import":       r"Could not find module|Module.*not found",
    "ambiguous_occurrence": r"Ambiguous occurrence",
    "wrong_controller":     r"controller.*not.*party",
    "missing_do":           r"do.*expected",
    "indentation_error":    r"indentation",
}


def run_compile_agent(daml_code: str, job_id: str) -> dict:
    settings = get_settings()
    project_dir = _create_project_dir(daml_code, job_id, settings.dar_output_dir)

    logger.info("Running compile agent", job_id=job_id, project_dir=project_dir)

    result = _run_daml_build(project_dir, settings.daml_sdk_path)

    if result["success"]:
        dar_path = _find_dar_file(project_dir)
        logger.info("Compilation succeeded", job_id=job_id, dar_path=dar_path)
        return {
            "success":  True,
            "dar_path": dar_path,
            "output":   result["stdout"],
            "errors":   [],
        }
    else:
        errors = _parse_errors(result["stderr"] + result["stdout"])
        logger.warning("Compilation failed", job_id=job_id, error_count=len(errors))
        return {
            "success":       False,
            "dar_path":      "",
            "output":        result["stderr"],
            "errors":        errors,
            "raw_error":     result["stderr"],
            "error_summary": _summarize_errors(errors),
        }


def _create_project_dir(daml_code: str, job_id: str, base_dir: str) -> str:
    project_dir = os.path.join(base_dir, f"ginie-{job_id}")
    daml_src_dir = os.path.join(project_dir, "daml")

    Path(daml_src_dir).mkdir(parents=True, exist_ok=True)

    with open(os.path.join(daml_src_dir, "Main.daml"), "w") as f:
        f.write(daml_code)

    with open(os.path.join(project_dir, "daml.yaml"), "w") as f:
        f.write(DAML_YAML_TEMPLATE.format(project_name=f"ginie-{job_id[:8]}"))

    return project_dir


def _run_daml_build(project_dir: str, daml_sdk_path: str) -> dict:
    try:
        proc = subprocess.run(
            [daml_sdk_path, "build", "--project-root", project_dir],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "DAML_PROJECT": project_dir},
        )
        return {
            "success": proc.returncode == 0,
            "stdout":  proc.stdout,
            "stderr":  proc.stderr,
            "code":    proc.returncode,
        }
    except FileNotFoundError:
        logger.warning("Daml SDK not found, running in mock mode", path=daml_sdk_path)
        return _mock_compile(project_dir)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout":  "",
            "stderr":  "Compilation timed out after 120 seconds",
            "code":    -1,
        }


def _mock_compile(project_dir: str) -> dict:
    main_daml = os.path.join(project_dir, "daml", "Main.daml")
    with open(main_daml, "r") as f:
        code = f.read()

    issues = []
    if "module " not in code:
        issues.append("Missing module declaration")
    if "signatory" not in code:
        issues.append("Missing signatory in template")
    if "template " not in code:
        issues.append("No template defined")

    if issues:
        return {
            "success": False,
            "stdout":  "",
            "stderr":  "Mock compile error: " + "; ".join(issues),
            "code":    1,
        }

    mock_dar = os.path.join(project_dir, ".daml", "dist", "output.dar")
    Path(os.path.dirname(mock_dar)).mkdir(parents=True, exist_ok=True)
    with open(mock_dar, "wb") as f:
        f.write(b"MOCK_DAR_" + code[:100].encode())

    return {
        "success": True,
        "stdout":  "Mock compilation succeeded",
        "stderr":  "",
        "code":    0,
    }


def _find_dar_file(project_dir: str) -> str:
    dist_dir = os.path.join(project_dir, ".daml", "dist")
    if os.path.exists(dist_dir):
        for f in os.listdir(dist_dir):
            if f.endswith(".dar"):
                return os.path.join(dist_dir, f)
    for root, _, files in os.walk(project_dir):
        for f in files:
            if f.endswith(".dar"):
                return os.path.join(root, f)
    return ""


def _parse_errors(error_output: str) -> list[dict]:
    errors = []
    lines = error_output.split("\n")

    line_pattern = re.compile(r"(\w+\.daml):(\d+):(\d+):\s*(.*)")

    i = 0
    while i < len(lines):
        line = lines[i]
        match = line_pattern.match(line)

        if match:
            file_name = match.group(1)
            line_num  = int(match.group(2))
            col_num   = int(match.group(3))
            message   = match.group(4)

            context_lines = []
            j = i + 1
            while j < len(lines) and j < i + 5:
                if not line_pattern.match(lines[j]) and lines[j].strip():
                    context_lines.append(lines[j])
                else:
                    break
                j += 1

            error_type = _classify_error(message + " " + " ".join(context_lines))

            errors.append({
                "file":        file_name,
                "line":        line_num,
                "column":      col_num,
                "message":     message,
                "context":     "\n".join(context_lines),
                "error_type":  error_type,
                "fixable":     _is_fixable(error_type),
                "raw":         "\n".join([line] + context_lines),
            })
        i += 1

    if not errors and error_output.strip():
        errors.append({
            "file":       "Main.daml",
            "line":       0,
            "column":     0,
            "message":    error_output[:500],
            "context":    "",
            "error_type": "unknown",
            "fixable":    True,
            "raw":        error_output[:1000],
        })

    return errors


def _classify_error(text: str) -> str:
    for error_type, pattern in ERROR_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return error_type
    return "unknown"


def _is_fixable(error_type: str) -> bool:
    architectural_errors = {"missing_signatory", "wrong_controller"}
    return error_type not in architectural_errors


def _summarize_errors(errors: list[dict]) -> str:
    if not errors:
        return "No errors"
    summary_parts = []
    for err in errors[:5]:
        loc = f"line {err['line']}" if err.get("line") else "unknown location"
        summary_parts.append(f"[{err.get('error_type', 'error')} at {loc}]: {err.get('message', '')[:100]}")
    return "\n".join(summary_parts)
