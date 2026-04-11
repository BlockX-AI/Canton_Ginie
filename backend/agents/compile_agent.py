import os
import re
import shutil
import subprocess
import structlog
from pathlib import Path

from config import get_settings
from daml.error_classifier import ErrorClassifier

logger = structlog.get_logger()

def _get_daml_yaml_template() -> str:
    from config import get_settings
    sdk_ver = get_settings().daml_sdk_version
    return f"""sdk-version: {sdk_ver}
name: {{project_name}}
version: 0.0.1
source: daml
dependencies:
  - daml-prim
  - daml-stdlib
"""

_SDK_INSTALL_INSTRUCTIONS = """
Daml SDK (daml CLI) is not installed or not on PATH.

Install via the Canton package manager (dpm):
    npm install -g @digitalasset/dpm
    dpm install daml-sdk

Or download the Canton binary directly:
    https://github.com/digital-asset/daml/releases

Then either:
  1. Add the SDK bin directory to your PATH, OR
  2. Set DAML_SDK_PATH=/path/to/daml in backend/.env.ginie

Start Canton sandbox with:
    canton sandbox --config canton-sandbox-memory.conf

After installing, restart the Ginie backend.
""".strip()

ERROR_PATTERNS = {
    "missing_signatory":    r"No signatory",
    "type_mismatch":        r"Couldn't match type|type mismatch",
    "parse_error":          r"parse error|Parse error",
    "unknown_variable":     r"Variable not in scope|Not in scope",
    "missing_import":       r"Could not find module|Module.*not found",
    "ambiguous_occurrence": r"Ambiguous occurrence",
    "multiple_ensure":      r"Multiple.*ensure|multiple.*ensure",
    "wrong_controller":     r"controller.*not.*party",
    "missing_do":           r"do.*expected",
    "indentation_error":    r"indentation",
}


def resolve_daml_sdk() -> str:
    settings = get_settings()
    candidates = [
        settings.daml_sdk_path,
        os.path.expanduser("~/.daml/bin/daml"),
        shutil.which("daml") or "",
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError(_SDK_INSTALL_INSTRUCTIONS)


def run_compile_agent(daml_code: str, job_id: str, *,
                      project_files: dict | None = None,
                      daml_yaml: str = "") -> dict:
    settings = get_settings()

    try:
        sdk_path = resolve_daml_sdk()
    except FileNotFoundError as exc:
        logger.error("Daml SDK not found", job_id=job_id)
        return {
            "success":       False,
            "dar_path":      "",
            "output":        "",
            "errors":        [{"file": "", "line": 0, "column": 0, "message": str(exc),
                               "error_type": "sdk_not_installed", "fixable": False, "raw": str(exc)}],
            "raw_error":     str(exc),
            "error_summary": str(exc),
        }

    project_dir = _create_project_dir(daml_code, job_id, settings.dar_output_dir,
                                       project_files=project_files, daml_yaml=daml_yaml)
    logger.info("Running compile agent", job_id=job_id, sdk=sdk_path, project_dir=project_dir)

    result = _run_daml_build(project_dir, sdk_path)

    if result["success"]:
        dar_path = _find_dar_file(project_dir)
        if not dar_path:
            logger.error("Build succeeded but no DAR found", job_id=job_id)
            return {
                "success":       False,
                "dar_path":      "",
                "output":        result["stdout"],
                "errors":        [{"file": "", "line": 0, "column": 0,
                                   "message": "Build process exited 0 but produced no DAR file.",
                                   "error_type": "no_dar_output", "fixable": False, "raw": ""}],
                "raw_error":     "No DAR produced",
                "error_summary": "No DAR file produced despite successful build exit code",
            }
        logger.info("Compilation succeeded", job_id=job_id, dar_path=dar_path)
        return {
            "success":  True,
            "dar_path": dar_path,
            "output":   result["stdout"],
            "errors":   [],
        }
    else:
        combined = (result["stderr"] + "\n" + result["stdout"]).strip()
        errors = _parse_errors(combined)
        logger.warning("Compilation failed", job_id=job_id, error_count=len(errors))
        return {
            "success":       False,
            "dar_path":      "",
            "output":        combined,
            "errors":        errors,
            "raw_error":     result["stderr"],
            "error_summary": _summarize_errors(errors),
        }


def _ensure_module_header(code: str) -> str:
    """Guarantee the code starts with module Main where."""
    has_module = re.search(r"^\s*module\s+\w+\s+where", code, re.MULTILINE)

    if not has_module:
        code = "module Main where\n\n" + code
    else:
        # Ensure module is named Main
        code = re.sub(r"^(\s*)module\s+\w+\s+where", r"\1module Main where", code, count=1, flags=re.MULTILINE)

    return code


def _sanitize_daml(code: str) -> str:
    code = _ensure_module_header(code)
    code = _fix_choice_ordering(code)
    code = _fix_this_dot_refs(code)
    code = _fix_bad_imports(code)
    code = _strip_script_blocks(code)
    lines = code.split("\n")
    result = []
    ensure_seen_in_template = False
    in_where_block = False
    pending_ensure: str | None = None

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        if stripped.startswith("template ") or stripped.startswith("interface "):
            ensure_seen_in_template = False
            in_where_block = False
            pending_ensure = None

        if stripped.startswith("where"):
            in_where_block = True

        if in_where_block and stripped.startswith("ensure "):
            if not ensure_seen_in_template:
                ensure_seen_in_template = True
                pending_ensure = line
                continue
            else:
                extra_cond = stripped[len("ensure "):].strip()
                if pending_ensure is not None:
                    prev_cond = pending_ensure.lstrip()[len("ensure "):].strip()
                    indent = len(pending_ensure) - len(pending_ensure.lstrip())
                    pending_ensure = " " * indent + f"ensure {prev_cond} && {extra_cond}"
                continue

        if pending_ensure is not None:
            result.append(pending_ensure)
            pending_ensure = None

        line = re.sub(r'\b([A-Z][a-zA-Z0-9_]*)\.([a-z][a-zA-Z0-9_]*)\b', _strip_module_qualifier, line)
        result.append(line)

    if pending_ensure is not None:
        result.append(pending_ensure)

    return "\n".join(result)


def _strip_script_blocks(code: str) -> str:
    """Remove all Script test functions and their imports."""
    # Remove Daml.Script import
    code = re.sub(r'^\s*import\s+Daml\.Script\b.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*import\s+DA\.Assert\b.*$', '', code, flags=re.MULTILINE)

    # Remove script function blocks: type annotation + function def + indented body
    # Pattern: funcName : Script (...)\nfuncName = script do\n  ...\n
    lines = code.split("\n")
    result = []
    skip_until_top_level = False
    skip_annotation = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect script type annotation: `name : Script (...)`
        if re.match(r'^[a-z]\w*\s*:\s*Script\b', stripped):
            skip_annotation = True
            continue

        # Detect script function: `name = script do`
        if re.match(r'^[a-z]\w*\s*=\s*script\s+do', stripped):
            skip_until_top_level = True
            skip_annotation = False
            continue

        # If we were skipping an annotation but next line is not the function, emit nothing
        if skip_annotation:
            if re.match(r'^[a-z]\w*\s*=\s*script\s+do', stripped):
                skip_until_top_level = True
                skip_annotation = False
                continue
            else:
                skip_annotation = False

        # While skipping a script body, skip indented lines
        if skip_until_top_level:
            if stripped == '' or line.startswith(' ') or line.startswith('\t'):
                continue
            else:
                skip_until_top_level = False

        result.append(line)

    return "\n".join(result)


def _fix_this_dot_refs(code: str) -> str:
    return re.sub(r'\bthis\.([a-z][a-zA-Z0-9_]*)\b', r'\1', code)


def _fix_bad_imports(code: str) -> str:
    bad_imports = {
        r'^import DA\.Decimal.*$',
        r'^import DA\.Numeric.*$',
    }
    lines = code.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if any(re.match(pat, stripped) for pat in bad_imports):
            continue
        result.append(line)
    return "\n".join(result)


def _fix_choice_ordering(code: str) -> str:
    controller_re = re.compile(r'^(\s*)controller\b(.*)$')
    with_block_re  = re.compile(r'^(\s*)with\s*$')

    lines = code.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        cm = controller_re.match(line)
        if cm:
            indent = cm.group(1)
            rest   = cm.group(2)
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


def _strip_module_qualifier(m: re.Match) -> str:
    qualified = m.group(0)
    template_name = m.group(1)
    field_name = m.group(2)
    daml_modules = {"Daml", "DA", "GHC", "Data", "Text", "Numeric", "Time", "Date", "Map", "Set", "Optional", "Either", "Script"}
    if template_name in daml_modules:
        return qualified
    return field_name


def _create_project_dir(daml_code: str, job_id: str, base_dir: str,
                        project_files: dict | None = None,
                        daml_yaml: str = "") -> str:
    """Create a project directory for ``daml build``.

    If *project_files* is provided (project mode), write each file separately.
    Otherwise fall back to single-file mode writing ``daml/Main.daml``.
    """
    project_dir = os.path.join(base_dir, f"ginie-{job_id}")
    daml_src_dir = os.path.join(project_dir, "daml")

    # Wipe source dir clean to avoid leftover files from prior attempts
    if os.path.exists(daml_src_dir):
        shutil.rmtree(daml_src_dir)
    Path(daml_src_dir).mkdir(parents=True, exist_ok=True)

    if project_files:
        # Project mode: write each file to its path
        for fpath, code in project_files.items():
            full_path = os.path.join(project_dir, fpath)
            Path(full_path).parent.mkdir(parents=True, exist_ok=True)
            sanitized = _sanitize_daml_project_file(code, fpath)
            with open(full_path, "w") as f:
                f.write(sanitized)
        logger.info("Project files written", file_count=len(project_files),
                    files=list(project_files.keys()))
    else:
        # Single-file mode
        sanitized = _sanitize_daml(daml_code)
        with open(os.path.join(daml_src_dir, "Main.daml"), "w") as f:
            f.write(sanitized)

    # Write daml.yaml
    yaml_content = daml_yaml if daml_yaml else _get_daml_yaml_template().format(project_name="ginie-project")
    with open(os.path.join(project_dir, "daml.yaml"), "w") as f:
        f.write(yaml_content)

    return project_dir


def _sanitize_daml_project_file(code: str, filepath: str) -> str:
    """Sanitize a single DAML file in project mode.

    Unlike single-file mode, we do NOT force module name to Main —
    we preserve the module name as-is.
    """
    code = _fix_choice_ordering(code)
    code = _fix_this_dot_refs(code)
    code = _fix_bad_imports(code)
    code = _strip_script_blocks(code)

    # Merge multiple ensure clauses
    lines = code.split("\n")
    result = []
    ensure_seen_in_template = False
    in_where_block = False
    pending_ensure: str | None = None

    for line in lines:
        stripped = line.lstrip()

        if stripped.startswith("template ") or stripped.startswith("interface "):
            ensure_seen_in_template = False
            in_where_block = False
            pending_ensure = None

        if stripped.startswith("where"):
            in_where_block = True

        if in_where_block and stripped.startswith("ensure "):
            if not ensure_seen_in_template:
                ensure_seen_in_template = True
                pending_ensure = line
                continue
            else:
                extra_cond = stripped[len("ensure "):].strip()
                if pending_ensure is not None:
                    prev_cond = pending_ensure.lstrip()[len("ensure "):].strip()
                    indent = len(pending_ensure) - len(pending_ensure.lstrip())
                    pending_ensure = " " * indent + f"ensure {prev_cond} && {extra_cond}"
                continue

        if pending_ensure is not None:
            result.append(pending_ensure)
            pending_ensure = None

        line = re.sub(r'\b([A-Z][a-zA-Z0-9_]*)\.([a-z][a-zA-Z0-9_]*)\b', _strip_module_qualifier, line)
        result.append(line)

    if pending_ensure is not None:
        result.append(pending_ensure)

    return "\n".join(result)


def _run_daml_build(project_dir: str, daml_sdk_path: str) -> dict:
    java_home = os.environ.get("JAVA_HOME", "/opt/homebrew/opt/openjdk")
    env = {
        **os.environ,
        "DAML_PROJECT": project_dir,
        "JAVA_HOME": java_home,
        "PATH": f"{java_home}/bin:{os.environ.get('PATH', '')}",
    }
    cmd = [daml_sdk_path, "build", "--project-root", project_dir]

    logger.info("Spawning daml build", cmd=" ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        logger.info(
            "daml build exited",
            code=proc.returncode,
            stdout_len=len(proc.stdout),
            stderr_len=len(proc.stderr),
        )
        return {
            "success": proc.returncode == 0,
            "stdout":  proc.stdout,
            "stderr":  proc.stderr,
            "code":    proc.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.error("daml build timed out", project_dir=project_dir)
        return {
            "success": False,
            "stdout":  "",
            "stderr":  "Compilation timed out after 180 seconds. Check for infinite loops or large dependency graphs.",
            "code":    -1,
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


async def run_compile_agent_sandbox(sandbox, project_name: str) -> dict:
    logger.info("Running sandbox compile agent", project_name=project_name)

    try:
        sdk_path = resolve_daml_sdk()
    except FileNotFoundError as exc:
        return {
            "compile_success": False,
            "dar_path": "",
            "compile_errors": [{"file": "", "line": 0, "column": 0, "type": "sdk_not_installed", "message": str(exc), "context": []}],
        }

    result = await sandbox.commands.run(f'"{sdk_path}" build --project-root .')

    if result["exit_code"] == 0:
        dar_path = f".daml/dist/{project_name}-0.0.1.dar"
        logger.info("Sandbox compilation succeeded", project_name=project_name, dar_path=dar_path)
        return {
            "compile_success": True,
            "dar_path": dar_path,
            "compile_errors": [],
        }

    combined = (result["stderr"] + "\n" + result["stdout"]).strip()
    classifier = ErrorClassifier()
    errors = classifier.parse_compile_output(combined)

    logger.warning(
        "Sandbox compilation failed",
        project_name=project_name,
        error_count=len(errors),
    )
    return {
        "compile_success": False,
        "dar_path": "",
        "compile_errors": errors,
    }
