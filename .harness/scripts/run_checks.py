"""Run every automated harness check and write a deterministic result file.

Usage::

    python .harness/scripts/run_checks.py --sprint 2     # full gate set for a sprint
    python .harness/scripts/run_checks.py --ci           # repo-wide gates only (A1-A7)

Writes ``.harness/output/checks.json`` and ``checks.md``. Exit code 0 when every check that
ran passed, 1 otherwise. The same inputs always produce the same PASS/FAIL per check - this
file is what makes the Evaluator's hard gates deterministic.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import contextlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_common import (
    OUTPUT,
    ROOT,
    SprintContract,
    changed_files,
    config,
    load_json,
    matches_any,
    parse_contract,
    write_json,
)

COVERAGE_JSON = OUTPUT / "coverage.json"
MAX_FINDINGS = 40
FINDING_LINE = re.compile(r"^(?P<file>[^\s:][^:]*\.py):(?P<line>\d+)(?::\d+)?:?\s*(?P<msg>.*)$")
BUILTIN_EXCEPTIONS = {
    name
    for name, obj in vars(builtins).items()
    if isinstance(obj, type) and issubclass(obj, BaseException)
}
BANNED_RAISES = BUILTIN_EXCEPTIONS | {"HTTPException"}


@dataclass
class Finding:
    file: str
    line: int
    message: str


@dataclass
class CheckResult:
    id: str
    status: str  # PASS | FAIL | SKIPPED
    summary: str
    command: str = ""
    findings: list[Finding] = field(default_factory=list)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    # wide COLUMNS stops rich-based tools (import-linter) wrapping file:line findings
    env = {**os.environ, "COLUMNS": "400", "NO_COLOR": "1"}
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False, env=env)


def _norm(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        with contextlib.suppress(ValueError):
            candidate = candidate.relative_to(ROOT)
    return candidate.as_posix()


def _parse_findings(output: str) -> list[Finding]:
    findings: list[Finding] = []
    for raw in output.splitlines():
        match = FINDING_LINE.match(raw.strip())
        if match:
            findings.append(Finding(_norm(match["file"]), int(match["line"]), match["msg"].strip()))
    return findings[:MAX_FINDINGS]


def _tail(output: str, lines: int = 15) -> list[Finding]:
    return [Finding("", 0, line) for line in output.strip().splitlines()[-lines:]]


def _tool_check(check_id: str, cmd: list[str], label: str) -> CheckResult:
    proc = _run(cmd)
    output = proc.stdout + proc.stderr
    status = "PASS" if proc.returncode == 0 else "FAIL"
    findings = [] if status == "PASS" else (_parse_findings(output) or _tail(output))
    summary = f"{label}: {'clean' if status == 'PASS' else f'exit {proc.returncode}'}"
    return CheckResult(
        check_id, status, summary, " ".join(cmd[1:] if cmd[0] == sys.executable else cmd), findings
    )


# -- A1-A5: external tools ------------------------------------------------------------


def check_ruff_lint() -> CheckResult:
    cmd = [sys.executable, "-m", "ruff", "check", ".", "--output-format=concise"]
    return _tool_check("A1", cmd, "ruff check")


def check_ruff_format() -> CheckResult:
    proc = _run([sys.executable, "-m", "ruff", "format", "--check", "."])
    if proc.returncode == 0:
        return CheckResult("A2", "PASS", "ruff format: clean", "ruff format --check .")
    findings: list[Finding] = []
    for line in proc.stdout.splitlines():
        legacy = line.split("Would reformat:", 1)
        arrow = re.search(r"-->\s+(\S+?):(\d+)", line)
        if len(legacy) == 2:
            findings.append(Finding(_norm(legacy[1].strip()), 1, "needs `ruff format`"))
        elif arrow:
            findings.append(Finding(_norm(arrow[1]), int(arrow[2]), "needs `ruff format`"))
    return CheckResult(
        "A2",
        "FAIL",
        "ruff format: files need formatting (run `ruff format .`)",
        "ruff format --check .",
        findings or _tail(proc.stdout + proc.stderr),
    )


def check_mypy() -> CheckResult:
    return _tool_check("A3", [sys.executable, "-m", "mypy"], "mypy --strict")


def check_pytest() -> CheckResult:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--cov",
        f"--cov-report=json:{COVERAGE_JSON.relative_to(ROOT).as_posix()}",
    ]
    proc = _run(cmd)
    output = proc.stdout + proc.stderr
    tail = next(
        (ln for ln in reversed(output.splitlines()) if re.search(r"\d+ (passed|failed|error)", ln)),
        "no test summary",
    ).strip()
    if proc.returncode == 0:
        return CheckResult("A4", "PASS", f"pytest: {tail}", "pytest --cov")
    failed = [
        Finding(_norm(line.split()[1].split("::")[0]), 0, line)
        for line in output.splitlines()
        if line.startswith(("FAILED ", "ERROR "))
    ]
    return CheckResult(
        "A4", "FAIL", f"pytest: {tail}", "pytest --cov", failed[:MAX_FINDINGS] or _tail(output)
    )


def check_import_linter() -> CheckResult:
    exe_dir = Path(sys.executable).parent
    exe = shutil.which("lint-imports", path=str(exe_dir)) or shutil.which("lint-imports")
    if exe is None:
        return CheckResult("A5", "FAIL", "lint-imports not installed (pip install -e .[dev])")
    proc = _run([exe, "--no-cache"])
    output = proc.stdout + proc.stderr
    if proc.returncode == 0:
        kept = next((line for line in output.splitlines() if line.startswith("Contracts:")), "")
        return CheckResult("A5", "PASS", f"import-linter: {kept}", "lint-imports")
    findings: list[Finding] = []
    for line in output.splitlines():
        match = re.match(
            r"^-?\s*(storeops\.[\w.]+) -> (storeops\.[\w.]+|\w[\w.]*) \(l\.(\d+)\)", line.strip()
        )
        if match:
            src = "src/" + match[1].replace(".", "/") + ".py"
            findings.append(Finding(src, int(match[3]), f"imports {match[2]}"))
        elif line.endswith("BROKEN"):
            findings.append(Finding("pyproject.toml", 0, line.strip()))
    return CheckResult(
        "A5",
        "FAIL",
        "import-linter: contract(s) BROKEN",
        "lint-imports",
        findings[:MAX_FINDINGS] or _tail(output),
    )


# -- A6: error contract ---------------------------------------------------------------


def _layer_of(path: Path) -> str | None:
    parts = path.relative_to(ROOT / "src" / "storeops" / "modules").parts
    if len(parts) < 2:
        return None
    stem = Path(parts[-1]).stem
    for layer in config()["error_contract_layers"]:
        if stem == layer or (len(parts) > 2 and parts[1] in {layer, f"{layer}s"}):
            return str(layer)
    return None


def check_error_contract() -> CheckResult:
    findings: list[Finding] = []
    for path in sorted((ROOT / "src" / "storeops" / "modules").rglob("*.py")):
        if _layer_of(path) is None:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            name = (
                exc.id
                if isinstance(exc, ast.Name)
                else exc.attr
                if isinstance(exc, ast.Attribute)
                else ""
            )
            if name in BANNED_RAISES:
                findings.append(
                    Finding(
                        _norm(str(path)),
                        node.lineno,
                        f"raises {name}; raise an AppError subclass from storeops.core.errors",
                    )
                )
    status = "FAIL" if findings else "PASS"
    return CheckResult(
        "A6",
        status,
        f"error contract: {len(findings)} raw raise(s) in service/routes",
        "ast scan",
        findings,
    )


# -- A7/A8: coverage ------------------------------------------------------------------


def _coverage_files() -> dict[str, tuple[int, int]] | None:
    if not COVERAGE_JSON.is_file():
        return None
    data = load_json(COVERAGE_JSON)
    files: dict[str, tuple[int, int]] = {}
    for name, info in data["files"].items():
        summary = info["summary"]
        files[_norm(name)] = (int(summary["num_statements"]), int(summary["covered_lines"]))
    return files


def _pct(stmts: int, covered: int) -> float:
    return 100.0 if stmts == 0 else round(100.0 * covered / stmts, 1)


def check_coverage_scopes() -> CheckResult:
    files = _coverage_files()
    if files is None:
        return CheckResult("A7", "FAIL", "coverage.json missing - A4 must run first")
    findings: list[Finding] = []
    parts: list[str] = []
    for scope, rule in config()["coverage_thresholds"].items():
        selected = [v for k, v in files.items() if matches_any(k, rule["globs"])]
        stmts = sum(s for s, _ in selected)
        covered = sum(c for _, c in selected)
        pct = _pct(stmts, covered)
        parts.append(f"{scope} {pct}% (min {rule['min_line_pct']})")
        if pct < rule["min_line_pct"]:
            findings.append(
                Finding("", 0, f"{scope} line coverage {pct}% < {rule['min_line_pct']}%")
            )
    return CheckResult(
        "A7",
        "FAIL" if findings else "PASS",
        "coverage: " + ", ".join(parts),
        "pytest --cov",
        findings,
    )


def check_changed_file_coverage(changed: list[str]) -> CheckResult:
    files = _coverage_files()
    if files is None:
        return CheckResult("A8", "FAIL", "coverage.json missing - A4 must run first")
    thresholds = config()["coverage_thresholds"]
    findings: list[Finding] = []
    checked = 0
    for path in changed:
        if path not in files:
            continue
        stmts, covered = files[path]
        if stmts == 0:
            continue
        scope = next(
            (
                s
                for s in ("service", "routes", "shared")
                if matches_any(path, thresholds[s]["globs"])
            ),
            "overall",
        )
        minimum = thresholds[scope]["min_line_pct"]
        pct = _pct(stmts, covered)
        checked += 1
        if pct < minimum:
            findings.append(Finding(path, 0, f"{scope} file line coverage {pct}% < {minimum}%"))
    return CheckResult(
        "A8",
        "FAIL" if findings else "PASS",
        f"changed-file coverage: {checked} file(s) checked",
        "pytest --cov",
        findings,
    )


# -- A9/A10: test quality -------------------------------------------------------------


def _is_behavioural(node: ast.AST, source: str) -> bool:
    if isinstance(node, ast.Assert):
        segment = ast.get_source_segment(source, node) or ""
        return "status_code" not in segment
    if isinstance(node, ast.Call):
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else ""
        )
        return name.startswith(("assert_", "expect_")) or name == "raises"
    return False


def check_assertion_quality(changed: list[str]) -> CheckResult:
    findings: list[Finding] = []
    test_files = [
        p for p in changed if re.match(r"^tests/(.+/)?test_[^/]+\.py$", p) and (ROOT / p).is_file()
    ]
    for rel in test_files:
        source = (ROOT / rel).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            is_test = node.name.startswith("test_")
            if is_test and not any(_is_behavioural(c, source) for c in ast.walk(node)):
                findings.append(
                    Finding(
                        rel,
                        node.lineno,
                        f"{node.name} asserts only on status_code (or nothing)",
                    )
                )
    summary = (
        f"assertion quality: {len(test_files)} changed test file(s), "
        f"{len(findings)} status-only test(s)"
    )
    return CheckResult("A9", "FAIL" if findings else "PASS", summary, "ast scan", findings)


def check_ac_traceability(contract: SprintContract | None) -> CheckResult:
    if contract is None:
        return CheckResult("A10", "FAIL", "sprint contract not found")
    if not contract.ac_ids:
        return CheckResult(
            "A10", "FAIL", f"{contract.path.name} declares no AC-{contract.sprint}.N ids"
        )
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").rglob("test_*.py"))
    missing = [ac for ac in contract.ac_ids if not re.search(rf"\b{re.escape(ac)}\b", corpus)]
    findings = [
        Finding("tests/", 0, f"{ac} is not referenced by any test (docstring or name)")
        for ac in missing
    ]
    found = len(contract.ac_ids) - len(missing)
    summary = f"AC traceability: {found}/{len(contract.ac_ids)} ACs referenced"
    return CheckResult("A10", "FAIL" if missing else "PASS", summary, "text scan", findings)


# -- A11: event wiring ----------------------------------------------------------------


def _module_source(module: str) -> str:
    base = ROOT / "src" / "storeops" / "modules" / module
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(base.rglob("*.py")))


def check_event_wiring(contract: SprintContract | None) -> CheckResult:
    if contract is None:
        return CheckResult("A11", "FAIL", "sprint contract not found")
    if not contract.emits and not contract.handles:
        return CheckResult(
            "A11", "PASS", "event wiring: contract declares no EMIT/HANDLE (n/a)", "text scan"
        )
    events_src = (ROOT / "src" / "storeops" / "core" / "events.py").read_text(encoding="utf-8")
    findings: list[Finding] = []
    for event, _module in [*contract.emits, *contract.handles]:
        if not re.search(rf"^class {event}\(DomainEvent\)", events_src, re.MULTILINE):
            findings.append(
                Finding(
                    "src/storeops/core/events.py", 0, f"{event} is not defined as a DomainEvent"
                )
            )
    for event, module in contract.emits:
        if not re.search(rf"\.publish\(\s*{event}\(", _module_source(module)):
            findings.append(
                Finding(
                    f"src/storeops/modules/{module}/",
                    0,
                    f"{module} never calls bus.publish({event}(...))",
                )
            )
    for event, module in contract.handles:
        if not re.search(rf"\.subscribe\(\s*{event}\s*,", _module_source(module)):
            findings.append(
                Finding(
                    f"src/storeops/modules/{module}/", 0, f"{module} never subscribes to {event}"
                )
            )
    summary = (
        f"event wiring: {len(contract.emits)} EMIT, {len(contract.handles)} HANDLE, "
        f"{len(findings)} missing"
    )
    return CheckResult("A11", "FAIL" if findings else "PASS", summary, "text scan", findings)


# -- A12: protected files -------------------------------------------------------------


def check_protected_files(changed: list[str], contract: SprintContract | None) -> CheckResult:
    cfg = config()
    approved = contract.approved_protected if contract else []
    findings = [
        Finding(path, 0, "protected file changed without an approved contract entry")
        for path in changed
        if matches_any(path, cfg["protected_paths"])
        and not matches_any(path, cfg["unprotected_harness_paths"])
        and path not in approved
    ]
    summary = f"protected files: {len(findings)} unapproved; approved = {approved or 'none'}"
    return CheckResult("A12", "FAIL" if findings else "PASS", summary, "git status", findings)


# -- driver ---------------------------------------------------------------------------


def run(sprint: int | None, ci: bool) -> list[CheckResult]:
    results = [
        check_ruff_lint(),
        check_ruff_format(),
        check_mypy(),
        check_pytest(),
        check_import_linter(),
        check_error_contract(),
        check_coverage_scopes(),
    ]
    if not ci and sprint is not None:
        changed = changed_files()
        contract = parse_contract(sprint)
        results += [
            check_changed_file_coverage(changed),
            check_assertion_quality(changed),
            check_ac_traceability(contract),
            check_event_wiring(contract),
            check_protected_files(changed, contract),
        ]
    else:
        results.extend(
            CheckResult(cid, "SKIPPED", "contract-scoped check (CI mode)")
            for cid in ("A8", "A9", "A10", "A11", "A12")
        )
    return results


def render_markdown(results: list[CheckResult]) -> str:
    lines = ["| Check | Status | Summary |", "|---|---|---|"]
    lines.extend(f"| {r.id} | {r.status} | {r.summary} |" for r in results)
    for r in results:
        if r.status == "FAIL" and r.findings:
            lines.append(f"\n### {r.id} findings")
            lines.extend(
                f"- `{f.file}:{f.line}` {f.message}" if f.file else f"- {f.message}"
                for f in r.findings
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sprint", type=int, help="sprint number (enables A8-A12)")
    parser.add_argument("--ci", action="store_true", help="repo-wide checks only")
    args = parser.parse_args()
    if args.sprint is None and not args.ci:
        parser.error("pass --sprint N or --ci")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = run(args.sprint, args.ci)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sprint": args.sprint,
        "mode": "ci" if args.ci else "sprint",
        "results": [asdict(r) for r in results],
    }
    write_json(OUTPUT / "checks.json", payload)
    markdown = render_markdown(results)
    (OUTPUT / "checks.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
