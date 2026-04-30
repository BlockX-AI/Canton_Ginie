"""Compile the Daml-Script test scaffold produced by ``test_writer_agent``.

Why a separate package?
-----------------------
The production DAR must NOT carry ``daml-script`` as a runtime
dependency \u2014 it bloats every Canton participant's package store and
exposes test scaffolding to the live ledger. Instead we build a *second*
project (``<name>-tests``) that imports the production DAR as a
data-dependency and adds ``daml-script`` only here. This mirrors the
pattern Digital Asset uses for their own demos.

Pipeline contract
-----------------
* Input : the just-compiled production DAR path + the test ``.daml`` source
  produced by ``test_writer_agent``.
* Output: ``{success, test_dar_path, test_compile_output, errors}`` \u2014
  on failure the pipeline does NOT abort; it logs a MEDIUM finding into
  ``audit_reports`` and continues.
* Side effects: writes a sibling project under
  ``<base_dir>/ginie-<job>-tests/`` mirroring ``compile_agent``\u2019s layout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import structlog

from agents.compile_agent import resolve_daml_sdk
from config import get_settings

logger = structlog.get_logger()


_TEST_DAML_YAML = """sdk-version: {sdk_version}
name: {project_name}-tests
version: 0.0.1
source: daml
dependencies:
  - daml-prim
  - daml-stdlib
  - daml-script
data-dependencies:
  - {production_dar_path}
"""


def run_test_compile_agent(
    *,
    job_id: str,
    production_dar_path: str,
    production_daml_code: str,
    test_daml_code: str,
    test_module_name: str,
    test_file_path: str,
) -> dict:
    """Compile the test scaffold against the production DAR.

    Returns a result dict with:
      * ``success``           : bool
      * ``test_dar_path``     : str  (empty on failure)
      * ``output``            : str  (combined stdout/stderr)
      * ``errors``            : list of {file, line, column, message}
      * ``test_compile_output_summary``: str  (1\u20132 line human summary)

    All failure paths are non-fatal: an upstream compile of the
    production code already succeeded, so we ship that DAR regardless
    of whether the test scaffold builds. Test-compile failures surface
    as a MEDIUM audit finding (handled by the caller).
    """
    settings = get_settings()

    if not production_dar_path or not os.path.exists(production_dar_path):
        return _fail(
            "production DAR missing \u2014 cannot anchor test data-dependency",
            job_id=job_id,
        )
    if not test_daml_code:
        return _fail("no test scaffold to compile", job_id=job_id, soft=True)

    try:
        sdk_path = resolve_daml_sdk()
    except FileNotFoundError as exc:
        return _fail(f"Daml SDK not available: {exc}", job_id=job_id)

    base_dir = tempfile.gettempdir()
    project_dir = os.path.join(base_dir, f"ginie-{job_id}-tests")
    daml_src_dir = os.path.join(project_dir, "daml")

    # Wipe & recreate so retries don't accumulate stale files.
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir, ignore_errors=True)
    Path(daml_src_dir).mkdir(parents=True, exist_ok=True)

    # Write the production module under its original name (test imports it
    # as `Main`). Then drop the test file at the path the test_writer
    # agent suggested (e.g. ``Test/ProposalTest.daml``). We deliberately
    # mirror the compile_agent\u2019s on-disk layout.
    with open(os.path.join(daml_src_dir, "Main.daml"), "w", encoding="utf-8") as f:
        f.write(production_daml_code)

    test_rel = test_file_path or f"{test_module_name.replace('.', '/')}.daml"
    test_abs = os.path.join(daml_src_dir, test_rel)
    Path(test_abs).parent.mkdir(parents=True, exist_ok=True)
    with open(test_abs, "w", encoding="utf-8") as f:
        f.write(test_daml_code)

    # Write daml.yaml with daml-script + production DAR data-dep.
    # Daml package names must match
    # ``^[A-Za-z][A-Za-z0-9]*(-[A-Za-z][A-Za-z0-9]*)*$`` \u2014 every
    # hyphen-separated segment has to *start* with a letter. UUID job
    # IDs like ``f8e80a8d-4321-...`` violate this because ``4321``
    # begins with a digit. We use a constant base name for the test
    # package (it is never published as a dependency, so collision is
    # not a concern) and only embed a sanitised job suffix for log
    # traceability.
    safe_suffix = "j" + "".join(c for c in job_id if c.isalnum())[:16]
    yaml_text = _TEST_DAML_YAML.format(
        sdk_version=settings.daml_sdk_version,
        project_name=f"ginie-tests-{safe_suffix}",
        # The data-dependencies path is relative to the project_dir.
        # We copy the DAR in so the path is short and portable.
        production_dar_path=os.path.basename(production_dar_path),
    )
    with open(os.path.join(project_dir, "daml.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml_text)

    try:
        shutil.copy2(production_dar_path,
                     os.path.join(project_dir, os.path.basename(production_dar_path)))
    except Exception as exc:
        return _fail(f"failed to stage production DAR: {exc}", job_id=job_id)

    proc_result = _run_build(project_dir, sdk_path)

    if not proc_result["success"]:
        logger.warning(
            "Test scaffold failed to compile",
            job_id=job_id,
            stdout_tail=proc_result["stdout"][-400:],
            stderr_tail=proc_result["stderr"][-400:],
        )
        return {
            "success":                       False,
            "test_dar_path":                 "",
            "output":                        proc_result["stdout"] + proc_result["stderr"],
            "errors":                        _parse_errors(proc_result["stderr"]),
            "test_compile_output_summary":   "Test scaffold did not compile (production DAR unaffected).",
        }

    test_dar = _find_dar(project_dir)
    if not test_dar:
        return _fail("build exited 0 but no test DAR produced", job_id=job_id)

    logger.info("Test scaffold compiled", job_id=job_id, test_dar=test_dar)

    # Phase F.1: optionally execute the Daml scripts in the test DAR.
    # ``daml test`` runs every ``script do`` block in the package and
    # aborts non-zero if any script fails an assert that was not wrapped
    # in ``submitMustFail``. Flag-gated so we can A/B against the
    # current pipeline before flipping the default. Default *on* in
    # production environments where the SDK is reliable; the flag
    # exists so a user with a flaky CI runner can opt out.
    if _scripts_enabled():
        script_outcome = _run_scripts(project_dir, sdk_path)
        return {
            "success":                       True,
            "test_dar_path":                 test_dar,
            "output":                        proc_result["stdout"],
            "errors":                        [],
            "test_compile_output_summary":   _summarise_script_outcome(script_outcome),
            "script_run_attempted":          True,
            "script_run_success":            script_outcome["success"],
            "script_run_summary":            script_outcome["summary"],
            "script_run_failures":           script_outcome["failures"],
            "script_run_output_tail":        script_outcome["output_tail"],
        }

    return {
        "success":                       True,
        "test_dar_path":                 test_dar,
        "output":                        proc_result["stdout"],
        "errors":                        [],
        "test_compile_output_summary":   "Test scaffold compiled successfully.",
        "script_run_attempted":          False,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_build(project_dir: str, sdk_path: str) -> dict:
    java_home = os.environ.get("JAVA_HOME", "/opt/homebrew/opt/openjdk")
    daml_bin_dir = os.path.dirname(sdk_path)
    path_sep = ";" if os.name == "nt" else ":"
    env = {
        **os.environ,
        "DAML_PROJECT": project_dir,
        "JAVA_HOME":    java_home,
        "PATH":         f"{daml_bin_dir}{path_sep}{java_home}/bin{path_sep}{os.environ.get('PATH', '')}",
    }
    cmd = [sdk_path, "build", "--project-root", project_dir]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        return {
            "success": proc.returncode == 0,
            "stdout":  proc.stdout or "",
            "stderr":  proc.stderr or "",
            "code":    proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout":  "",
            "stderr":  "test build timed out after 180s",
            "code":    -1,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "stdout":  "",
            "stderr":  f"test build crashed: {exc}",
            "code":    -1,
        }


# ---------------------------------------------------------------------------
# Phase F.1: Daml-Script execution
# ---------------------------------------------------------------------------


def _scripts_enabled() -> bool:
    """Phase F.1 is gated by ``RUN_DAML_SCRIPTS``.

    Default OFF for safety \u2014 running ``daml test`` adds 10\u201360s
    to every job and requires a working JVM + sandbox at compile-time.
    Set ``RUN_DAML_SCRIPTS=true`` (or ``1``, ``yes``, ``on``) to opt in.
    """
    return os.environ.get("RUN_DAML_SCRIPTS", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


# Recognised runtime failure markers in ``daml test`` output. Each is
# a substring search (not a regex) for speed and predictability.
# These cover Daml 2.x and 3.x.
_RUNTIME_FAIL_MARKERS = (
    "ENSURE_VIOLATED",
    "REQUIRES_AUTHORITATIVE",
    "AUTHORIZATION_FAILED",
    "ASSERTION_FAILED",
    "Aborted:",
    "Pretty.PrettyError",
    "Script execution failed",
    "Test failed",
    "[Error]",
)


def _run_scripts(project_dir: str, sdk_path: str) -> dict:
    """Run ``daml test`` against the freshly-built test package.

    Returns a dict with:
      * ``success``      : bool   - all scripts passed
      * ``returncode``   : int
      * ``output_tail``  : str    - last ~2000 chars of combined output
      * ``summary``      : str    - 1-2 line human summary
      * ``failures``     : list   - parsed runtime failures, each
                                    ``{"script": str, "marker": str, "context": str}``
    """
    java_home    = os.environ.get("JAVA_HOME", "/opt/homebrew/opt/openjdk")
    daml_bin_dir = os.path.dirname(sdk_path)
    path_sep     = ";" if os.name == "nt" else ":"
    env = {
        **os.environ,
        "DAML_PROJECT": project_dir,
        "JAVA_HOME":    java_home,
        "PATH":         f"{daml_bin_dir}{path_sep}{java_home}/bin{path_sep}{os.environ.get('PATH', '')}",
    }
    # ``daml test --color no --junit <file>`` would give us structured
    # results, but the JUnit emitter writes to disk and we'd have to
    # parse XML. The plain ``daml test`` stdout is reliable enough for
    # a pass/fail signal and we extract failure detail by substring
    # search on the output. Wall-clock cap: 90s.
    cmd = [sdk_path, "test", "--color", "no"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
            cwd=project_dir,
        )
    except subprocess.TimeoutExpired:
        return {
            "success":     False,
            "returncode":  -1,
            "output_tail": "daml test timed out after 90s",
            "summary":     "Test execution timed out after 90s.",
            "failures":    [{"script": "(timeout)", "marker": "TIMEOUT", "context": ""}],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success":     False,
            "returncode":  -1,
            "output_tail": f"daml test crashed: {exc}",
            "summary":     f"Test execution crashed: {exc}",
            "failures":    [{"script": "(crash)", "marker": "CRASH", "context": str(exc)}],
        }

    combined  = (proc.stdout or "") + "\n" + (proc.stderr or "")
    tail      = combined[-2000:]
    failures  = _parse_runtime_failures(combined)
    success   = proc.returncode == 0 and not failures

    if success:
        summary = "All Daml scripts passed."
    elif failures:
        # Pluck the first failure for a punchy human summary; full list
        # is in ``failures``.
        f0 = failures[0]
        summary = (
            f"Test runtime failure: {f0.get('marker', '?')} in "
            f"{f0.get('script', '<unknown>')}. "
            f"{len(failures) - 1} additional failure(s) suppressed."
            if len(failures) > 1
            else f"Test runtime failure: {f0.get('marker', '?')} in "
                 f"{f0.get('script', '<unknown>')}."
        )
    else:
        summary = f"Test execution exited with code {proc.returncode}."

    return {
        "success":     success,
        "returncode":  proc.returncode,
        "output_tail": tail,
        "summary":     summary,
        "failures":    failures,
    }


def _parse_runtime_failures(output: str) -> list[dict]:
    """Pull failure tuples out of ``daml test`` output.

    Daml prints each failing script on a line like
    ``daml/Test/FooTest.daml:run: FAILURE`` followed by an indented
    error trace. We anchor on those headers and capture the next 6
    non-blank lines as ``context``, then look for any of the
    ``_RUNTIME_FAIL_MARKERS`` to label the failure mode.
    """
    failures: list[dict] = []
    lines = output.splitlines()
    n = len(lines)
    header_re = __import__("re").compile(
        r"^(?P<file>[^\s:]+\.daml):(?P<script>[\w']+):\s*(?:FAIL|FAILURE|fail)",
        __import__("re").IGNORECASE,
    )
    for i, ln in enumerate(lines):
        m = header_re.match(ln.strip())
        if not m:
            continue
        ctx_lines = []
        for j in range(i + 1, min(i + 12, n)):
            if not lines[j].strip():
                continue
            ctx_lines.append(lines[j])
            if len(ctx_lines) >= 6:
                break
        ctx_blob = "\n".join(ctx_lines)
        marker = next(
            (mk for mk in _RUNTIME_FAIL_MARKERS if mk in ctx_blob),
            "UNCLASSIFIED",
        )
        failures.append({
            "script":  f"{m.group('file')}:{m.group('script')}",
            "marker":  marker,
            "context": ctx_blob[:1000],
        })
    # Fallback: if no header was found but the output contains a
    # runtime marker, surface it as a single anonymous failure so the
    # caller still knows something went wrong.
    if not failures:
        for mk in _RUNTIME_FAIL_MARKERS:
            if mk in output:
                idx = output.index(mk)
                ctx = output[max(0, idx - 200): idx + 400]
                failures.append({
                    "script":  "<unidentified>",
                    "marker":  mk,
                    "context": ctx,
                })
                break
    return failures


def _summarise_script_outcome(outcome: dict) -> str:
    """Compose the user-visible test_compile_summary string."""
    if outcome["success"]:
        return "Test scaffold compiled and all scripts passed."
    return (
        "Test scaffold compiled but script execution failed: "
        + outcome["summary"]
    )


def _find_dar(project_dir: str) -> str:
    dist = os.path.join(project_dir, ".daml", "dist")
    if not os.path.isdir(dist):
        return ""
    for name in os.listdir(dist):
        if name.endswith(".dar"):
            return os.path.join(dist, name)
    return ""


_ERROR_HEAD_RE = __import__("re").compile(
    r"^(?P<file>[^:\n]+\.daml):(?P<line>\d+):(?P<col>\d+):\s*(?P<msg>.+)$",
    __import__("re").MULTILINE,
)


def _parse_errors(stderr: str) -> list[dict]:
    out: list[dict] = []
    for m in _ERROR_HEAD_RE.finditer(stderr or ""):
        out.append({
            "file":    m.group("file"),
            "line":    int(m.group("line")),
            "column":  int(m.group("col")),
            "message": m.group("msg").strip(),
        })
    return out[:25]  # cap so a flood of warnings doesn't bloat the result


def _fail(reason: str, *, job_id: str, soft: bool = False) -> dict:
    """Build a uniform failure response. ``soft`` failures are non-issues
    (e.g. there was no test code to compile) and don't create findings.
    """
    if not soft:
        logger.warning("Test compile skipped", job_id=job_id, reason=reason)
    return {
        "success":                     False,
        "test_dar_path":               "",
        "output":                      "",
        "errors":                      [{"file": "", "line": 0, "column": 0,
                                          "message": reason}],
        "test_compile_output_summary": reason,
        "soft_failure":                soft,
    }
