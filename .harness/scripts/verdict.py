"""Compute the sprint verdict from per-check results. The Evaluator never chooses the verdict.

Inputs:
  .harness/output/checks.json            automated results (run_checks.py --sprint N)
  .harness/output/evaluator-checks.json  LLM-assessed results written by the Evaluator
  .harness/skills/grading-criteria/rubric.json

Usage::

    python .harness/scripts/verdict.py --sprint 1 --iteration 2 [--fallback]

Writes ``verdict.json`` and inserts/replaces the VERDICT block in ``evaluator-feedback.md``.
Exit 0 = verdict computed, 2 = Evaluator output INVALID (orchestrator re-runs the Evaluator
once, then re-invokes with ``--fallback`` which scores every missing/invalid LLM check FAIL).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from harness_common import OUTPUT, load_json, rubric, write_json

FEEDBACK = OUTPUT / "evaluator-feedback.md"
BEGIN, END = "<!-- VERDICT:BEGIN -->", "<!-- VERDICT:END -->"
RESULTS = {"PASS", "FAIL"}


@dataclass
class Scored:
    id: str
    dimension: str
    type: str
    severity: str
    points: int
    result: str
    reason: str


def _load_llm(path: Path, sprint: int, iteration: int) -> tuple[dict[str, Any], list[str]]:
    """Return {check_id: entry} and a list of problems that make the file INVALID."""
    if not path.is_file():
        return {}, [f"{path.name} not written"]
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        return {}, [f"{path.name} is not valid JSON: {exc}"]
    problems: list[str] = []
    if data.get("sprint") != sprint or data.get("iteration") != iteration:
        problems.append(
            f"{path.name} is for sprint/iteration {data.get('sprint')}/{data.get('iteration')}"
        )
    entries: dict[str, Any] = {}
    for entry in data.get("checks", []):
        cid = entry.get("id")
        if cid in entries:
            problems.append(f"{cid} reported twice")
        elif entry.get("result") not in RESULTS:
            problems.append(f"{cid} result must be PASS or FAIL, got {entry.get('result')!r}")
        else:
            entries[cid] = entry
    return entries, problems


def _score(
    sprint: int, iteration: int, fallback: bool
) -> tuple[list[Scored], list[str], list[str]]:
    checks = load_json(OUTPUT / "checks.json")
    problems: list[str] = []
    if checks.get("sprint") != sprint or checks.get("mode") != "sprint":
        problems.append("checks.json is stale - rerun run_checks.py --sprint N")
    auto = {r["id"]: r for r in checks["results"]}
    llm, llm_problems = _load_llm(OUTPUT / "evaluator-checks.json", sprint, iteration)
    problems += llm_problems
    warnings: list[str] = []
    scored: list[Scored] = []
    for dim in rubric()["dimensions"]:
        for check in dim["checks"]:
            cid = check["id"]
            if check["type"] == "automated":
                entry = auto.get(cid)
                result = entry["status"] if entry else "FAIL"
                result = "PASS" if result == "PASS" else "FAIL"
                reason = entry["summary"] if entry else "missing from checks.json"
            else:
                entry = llm.get(cid)
                if entry is None:
                    problems.append(f"{cid} missing from evaluator-checks.json")
                    result, reason = "FAIL", "ambiguous: Evaluator gave no result (fallback FAIL)"
                else:
                    result, reason = entry["result"], entry.get("reason", "")
                    evidence = [e for e in entry.get("evidence", []) if e.get("file")]
                    if not evidence:
                        if result == "PASS":
                            result, reason = (
                                "FAIL",
                                "PASS claimed without file evidence (evidence-or-fail)",
                            )
                        warnings.append(f"{cid}: no file:line evidence")
            scored.append(
                Scored(
                    cid,
                    dim["id"],
                    check["type"],
                    check["severity"],
                    check["points"],
                    result,
                    reason,
                )
            )
    if fallback:
        warnings += [f"fallback applied: {p}" for p in problems]
        problems = []
    return scored, problems, warnings


def compute(sprint: int, iteration: int, fallback: bool) -> dict[str, Any]:
    scored, problems, warnings = _score(sprint, iteration, fallback)
    if problems:
        return {
            "sprint": sprint,
            "iteration": iteration,
            "verdict": "INVALID",
            "problems": problems,
        }
    rules = rubric()["verdict_rules"]
    dims: list[dict[str, Any]] = []
    total = 0.0
    for dim in rubric()["dimensions"]:
        mine = [s for s in scored if s.dimension == dim["id"]]
        earned = sum(s.points for s in mine if s.result == "PASS")
        possible = sum(s.points for s in mine)
        pct = round(100.0 * earned / possible, 1) if possible else 100.0
        total += pct * dim["weight"] / 100.0
        dims.append({"id": dim["id"], "name": dim["name"], "weight": dim["weight"], "score": pct})
    total = round(total, 1)
    failed = [s for s in scored if s.result == "FAIL"]
    hard_failed = [s.id for s in failed if s.severity == "hard"]
    blocking_severity = [
        s.id for s in failed if s.severity in rules["pass_forbids_failed_severity"]
    ]
    if (hard_failed and rules["fail_if_any_hard_gate_fails"]) or total < rules["fail_below_score"]:
        verdict = "FAIL"
    elif total >= rules["pass_min_score"] and not blocking_severity:
        verdict = "PASS"
    else:
        verdict = "CONDITIONAL PASS"
    return {
        "sprint": sprint,
        "iteration": iteration,
        "verdict": verdict,
        "score": total,
        "dimensions": dims,
        "hard_gates_failed": hard_failed,
        "failed_checks": [s.id for s in failed],
        "checks": [asdict(s) for s in scored],
        "fallback": fallback,
        "warnings": warnings,
    }


def render(result: dict[str, Any]) -> str:
    lines = [BEGIN, f"VERDICT: {result['verdict']}"]
    if result["verdict"] == "INVALID":
        lines += [
            "",
            "Evaluator output could not be scored:",
            *[f"- {p}" for p in result["problems"]],
        ]
        return "\n".join([*lines, END])
    lines += [
        f"SCORE: {result['score']} / 100",
        f"HARD GATES FAILED: {', '.join(result['hard_gates_failed']) or 'none'}",
        "",
        "| Dimension | Weight | Score |",
        "|---|---|---|",
        *[
            f"| {d['id']} {d['name']} | {d['weight']}% | {d['score']} |"
            for d in result["dimensions"]
        ],
        "",
        "| Check | Severity | Result | Reason |",
        "|---|---|---|---|",
        *[
            f"| {c['id']} | {c['severity']} | {c['result']} | {c['reason']} |"
            for c in result["checks"]
        ],
    ]
    if result["warnings"]:
        lines += ["", "Warnings:", *[f"- {w}" for w in result["warnings"]]]
    return "\n".join([*lines, END])


def write_feedback_block(block: str) -> None:
    text = FEEDBACK.read_text(encoding="utf-8") if FEEDBACK.is_file() else "# Evaluator feedback\n"
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        text = head + block + rest.split(END, 1)[1]
    else:
        first, _, remainder = text.partition("\n")
        text = f"{first}\n\n{block}\n{remainder}"
    FEEDBACK.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sprint", type=int, required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--fallback", action="store_true")
    args = parser.parse_args()
    result = compute(args.sprint, args.iteration, args.fallback)
    write_json(OUTPUT / "verdict.json", result)
    block = render(result)
    write_feedback_block(block)
    print(block)
    return 2 if result["verdict"] == "INVALID" else 0


if __name__ == "__main__":
    sys.exit(main())
