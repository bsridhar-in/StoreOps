"""Harness state machine: sprint/iteration bookkeeping, routing decisions and run statistics.

Commands (all print JSON the orchestrator acts on)::

    route.py init --feature "<prompt>" --slug <kebab> --sprints <N>
    route.py begin                      # start the next Generator iteration of the current sprint
    route.py decide                     # verdict.json -> RETRY | ADVANCE | COMPLETE | ESCALATE
    route.py reset                      # after escalation: RESUME / RETRY SPRINT restart the sprint
    route.py stats --sprint <N>         # token/iteration estimate for the Monitor
    route.py status

Routing is deterministic: the same verdict history always yields the same action.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_common import (
    HARNESS,
    OUTPUT,
    REVIEWS,
    ROOT,
    changed_files,
    config,
    contract_path,
    load_json,
    write_json,
)

STATE = OUTPUT / "state.json"
HISTORY = OUTPUT / "history"
ITERATION_FILES = (
    "generator-summary.md",
    "evaluator-feedback.md",
    "evaluator-checks.json",
    "checks.json",
    "checks.md",
    "verdict.json",
)
SKILL_REF = re.compile(r"\.harness/skills/[\w-]+/SKILL\.md")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _state() -> dict[str, Any]:
    if not STATE.is_file():
        sys.exit("no harness run in progress - run `route.py init` first")
    data: dict[str, Any] = load_json(STATE)
    return data


def _current(state: dict[str, Any]) -> dict[str, Any]:
    sprint: dict[str, Any] = state["sprints"][state["current"] - 1]
    return sprint


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2))
    return 0


def cmd_init(feature: str, slug: str, sprints: int) -> int:
    run_id = f"{datetime.now(UTC):%Y%m%d-%H%M}-{slug}"
    state = {
        "run_id": run_id,
        "feature": feature,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "base_commit": _git("rev-parse", "HEAD"),
        "started_at": _now(),
        "max_iterations": config()["max_iterations_per_sprint"],
        "current": 1,
        "status": "running",
        "sprints": [
            {"n": n, "status": "pending", "iterations": 0, "evaluator_reruns": 0, "history": []}
            for n in range(1, sprints + 1)
        ],
    }
    missing = [n for n in range(1, sprints + 1) if not contract_path(n).is_file()]
    if missing:
        sys.exit(f"missing sprint contract(s): {missing}")
    write_json(STATE, state)
    archived = _archive_spec_and_contracts(run_id, sprints)
    return _emit(
        {"action": "INITIALISED", "run_id": run_id, "sprints": sprints, "archived": archived}
    )


def _archive_spec_and_contracts(run_id: str, sprints: int) -> list[str]:
    """Freeze the approved spec and sprint contracts into the committed audit trail.

    Called once, at `init` time (after approval mints the run id) - .harness/output/ stays
    scratch for the agents' working copies, but .harness/reviews/<run_id>/ keeps a permanent,
    point-in-time record alongside the Monitor's run-logs for the same run.
    """
    target = REVIEWS / run_id
    target.mkdir(parents=True, exist_ok=True)
    sources = [OUTPUT / "spec.md", *(contract_path(n) for n in range(1, sprints + 1))]
    for source in sources:
        shutil.copy2(source, target / source.name)
    return [p.relative_to(ROOT).as_posix() for p in sources]


def cmd_begin() -> int:
    state = _state()
    sprint = _current(state)
    if sprint["iterations"] >= state["max_iterations"]:
        sys.exit(f"sprint {sprint['n']} already used {sprint['iterations']} iterations")
    sprint["iterations"] += 1
    sprint["evaluator_reruns"] = 0
    sprint["status"] = "in_progress"
    write_json(STATE, state)
    for name in ("evaluator-checks.json", "verdict.json", "checks.json", "checks.md"):
        (OUTPUT / name).unlink(missing_ok=True)
    return _emit(
        {
            "action": "RUN_GENERATOR",
            "sprint": sprint["n"],
            "iteration": sprint["iterations"],
            "contract": contract_path(sprint["n"]).relative_to(ROOT).as_posix(),
            "feedback": (
                ".harness/output/evaluator-feedback.md" if sprint["iterations"] > 1 else None
            ),
        }
    )


def _archive(run_id: str, sprint: int, iteration: int) -> None:
    """Copy this iteration's Generator/Evaluator output to its scratch and permanent homes.

    The scratch copy (.harness/output/history/) is what the Generator and Monitor read
    during the run. The permanent copy (.harness/reviews/<run_id>/) is the committed audit
    trail - it survives the next `@planner` run clearing .harness/output/.
    """
    scratch = HISTORY / f"sprint-{sprint}" / f"iter-{iteration}"
    permanent = REVIEWS / run_id / f"sprint-{sprint}" / f"iter-{iteration}"
    scratch.mkdir(parents=True, exist_ok=True)
    permanent.mkdir(parents=True, exist_ok=True)
    for name in ITERATION_FILES:
        source = OUTPUT / name
        if source.is_file():
            shutil.copy2(source, scratch / name)
            shutil.copy2(source, permanent / name)


def _write_escalation(state: dict[str, Any], sprint: dict[str, Any], reason: str) -> Path:
    verdict = load_json(OUTPUT / "verdict.json")
    checks = {c["id"]: c for c in verdict.get("checks", [])}
    order = {"hard": 0, "major": 1}
    blocking = sorted(
        (checks[c] for c in verdict.get("failed_checks", []) if checks[c]["severity"] in order),
        key=lambda check: order[check["severity"]],
    )
    automated = {r["id"]: r for r in load_json(OUTPUT / "checks.json")["results"]}
    lines = [
        "# Harness escalation",
        "",
        "STATUS: ESCALATED - developer action required",
        "",
        f"- Run: `{state['run_id']}`  Feature: {state['feature']}",
        f"- Sprint: {sprint['n']} (`{contract_path(sprint['n']).name}`)",
        f"- Iterations used: {sprint['iterations']} of {state['max_iterations']}",
        f"- Reason: {reason}",
        f"- Last verdict: {verdict['verdict']} (score {verdict.get('score')})",
        "",
        "## Blocking issues",
    ]
    for check in blocking:
        lines.append(f"- **{check['id']}** ({check['severity']}): {check['reason']}")
        for finding in automated.get(check["id"], {}).get("findings", [])[:5]:
            where = f"`{finding['file']}:{finding['line']}` " if finding["file"] else ""
            lines.append(f"  - {where}{finding['message']}")
    lines += [
        "",
        "## Iteration history",
        "| Iteration | Verdict | Score | Failed checks |",
        "|---|---|---|---|",
        *[
            f"| {h['iteration']} | {h['verdict']} | {h['score']} | {', '.join(h['failed'])} |"
            for h in sprint["history"]
        ],
        "",
        "Full feedback per iteration (permanent copy; may not be committed until a sprint "
        f"passes): `.harness/reviews/{state['run_id']}/sprint-{sprint['n']}/iter-*/"
        "evaluator-feedback.md`",
        "",
        "## Developer options",
        "1. Fix the blocking issue by hand, then type `RESUME` (runs the Evaluator only).",
        "2. Amend the sprint contract (e.g. approve a boundary change), then type `RETRY SPRINT` "
        "(resets the iteration count for this sprint).",
        "3. Type `ABORT` to stop the run; completed sprints stay committed.",
    ]
    path = OUTPUT / "escalation.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def cmd_decide() -> int:
    state = _state()
    sprint = _current(state)
    verdict = load_json(OUTPUT / "verdict.json")
    if verdict["sprint"] != sprint["n"] or verdict["iteration"] != sprint["iterations"]:
        sys.exit("verdict.json does not match the current sprint/iteration")

    if verdict["verdict"] == "INVALID":
        sprint["evaluator_reruns"] += 1
        write_json(STATE, state)
        action = "RERUN_EVALUATOR" if sprint["evaluator_reruns"] == 1 else "RECOMPUTE_WITH_FALLBACK"
        return _emit({"action": action, "problems": verdict["problems"]})

    _archive(state["run_id"], sprint["n"], sprint["iterations"])
    previous = sprint["history"][-1] if sprint["history"] else None
    entry = {
        "iteration": sprint["iterations"],
        "verdict": verdict["verdict"],
        "score": verdict["score"],
        "failed": verdict["failed_checks"],
        "fallback": verdict["fallback"],
        "at": _now(),
    }
    sprint["history"].append(entry)
    at_cap = sprint["iterations"] >= state["max_iterations"]
    last_sprint = sprint["n"] == len(state["sprints"])
    no_progress = (
        previous is not None
        and verdict["verdict"] == "FAIL"
        and set(previous["failed"]) == set(verdict["failed_checks"])
        and verdict["score"] <= previous["score"]
    )

    if verdict["verdict"] == "FAIL" and (at_cap or no_progress):
        reason = (
            f"FAIL after {sprint['iterations']} iteration(s) (cap {state['max_iterations']})"
            if at_cap
            else "no progress: identical failing checks and no score improvement"
        )
        sprint["status"] = "escalated"
        state["status"] = "escalated"
        path = _write_escalation(state, sprint, reason)
        write_json(STATE, state)
        return _emit(
            {
                "action": "ESCALATE",
                "sprint": sprint["n"],
                "reason": reason,
                "escalation": path.relative_to(ROOT).as_posix(),
                "run_monitor": True,
            }
        )

    if verdict["verdict"] == "FAIL" or (verdict["verdict"] == "CONDITIONAL PASS" and not at_cap):
        sprint["status"] = "retry"
        write_json(STATE, state)
        return _emit(
            {
                "action": "RETRY",
                "sprint": sprint["n"],
                "next_iteration": sprint["iterations"] + 1,
                "verdict": verdict["verdict"],
            }
        )

    sprint["status"] = "passed" if verdict["verdict"] == "PASS" else "passed_with_conditions"
    if last_sprint:
        state["status"] = "complete"
    else:
        state["current"] += 1
    write_json(STATE, state)
    return _emit(
        {
            "action": "COMPLETE" if last_sprint else "ADVANCE",
            "sprint": sprint["n"],
            "verdict": verdict["verdict"],
            "run_monitor": True,
            "commit": True,
            "next_sprint": None if last_sprint else state["current"],
        }
    )


def cmd_reset() -> int:
    state = _state()
    sprint = _current(state)
    if sprint["status"] != "escalated":
        sys.exit(f"sprint {sprint['n']} is {sprint['status']}, not escalated")
    sprint.setdefault("previous_attempts", []).append(sprint["history"])
    sprint.update({"status": "pending", "iterations": 0, "evaluator_reruns": 0, "history": []})
    state["status"] = "running"
    write_json(STATE, state)
    (OUTPUT / "escalation.md").unlink(missing_ok=True)
    return _emit({"action": "RESET", "sprint": sprint["n"]})


def _chars(paths: list[Path]) -> int:
    return sum(p.stat().st_size for p in paths if p.is_file())


def _agent_reads(agent: str) -> list[Path]:
    agent_file = HARNESS / "agents" / f"{agent}.agent.md"
    skills = sorted(set(SKILL_REF.findall(agent_file.read_text(encoding="utf-8"))))
    return [agent_file, *(ROOT / s for s in skills)]


def cmd_stats(sprint_n: int) -> int:
    state = _state()
    sprint = state["sprints"][sprint_n - 1]
    cfg = config()["token_estimate"]
    code = [ROOT / p for p in changed_files() if p.endswith(".py")]
    history = HISTORY / f"sprint-{sprint_n}"
    per_iteration: list[dict[str, Any]] = []
    for k in range(1, sprint["iterations"] + 1):
        it = history / f"iter-{k}"
        gen_in = [*_agent_reads("generator"), contract_path(sprint_n), OUTPUT / "spec.md", *code]
        if k > 1:
            gen_in.append(history / f"iter-{k - 1}" / "evaluator-feedback.md")
        gen_out = [it / "generator-summary.md", *code]
        eval_in = [
            *_agent_reads("evaluator"),
            contract_path(sprint_n),
            it / "generator-summary.md",
            it / "checks.md",
            *code,
        ]
        eval_out = [it / "evaluator-feedback.md", it / "evaluator-checks.json"]
        chars = _chars(gen_in) + _chars(gen_out) + _chars(eval_in) + _chars(eval_out)
        tokens = chars // cfg["chars_per_token"] + 2 * cfg["agent_overhead_tokens"]
        per_iteration.append({"iteration": k, "estimated_tokens": tokens})
    monitor = (
        _chars(_agent_reads("monitor")) // cfg["chars_per_token"] + cfg["agent_overhead_tokens"]
    )
    planner = 0
    if sprint_n == 1:
        planner_in = [*_agent_reads("planner"), OUTPUT / "spec.md"]
        planner_in += [contract_path(s["n"]) for s in state["sprints"]]
        planner = _chars(planner_in) // cfg["chars_per_token"] + cfg["agent_overhead_tokens"]
    total = sum(i["estimated_tokens"] for i in per_iteration) + monitor + planner
    rate = cfg["blended_usd_per_mtok"]
    return _emit(
        {
            "sprint": sprint_n,
            "iterations": sprint["iterations"],
            "status": sprint["status"],
            "history": sprint["history"],
            "per_iteration": per_iteration,
            "planner_tokens": planner,
            "monitor_tokens": monitor,
            "estimated_total_tokens": total,
            "estimated_usd": round(total / 1_000_000 * rate, 2) if rate else None,
            "method": "file chars / chars_per_token + fixed per-agent overhead (estimate only)",
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init")
    init.add_argument("--feature", required=True)
    init.add_argument("--slug", required=True)
    init.add_argument("--sprints", type=int, required=True)
    sub.add_parser("begin")
    sub.add_parser("decide")
    sub.add_parser("reset")
    stats = sub.add_parser("stats")
    stats.add_argument("--sprint", type=int, required=True)
    sub.add_parser("status")
    args = parser.parse_args()

    if args.cmd == "init":
        return cmd_init(args.feature, args.slug, args.sprints)
    if args.cmd == "begin":
        return cmd_begin()
    if args.cmd == "decide":
        return cmd_decide()
    if args.cmd == "reset":
        return cmd_reset()
    if args.cmd == "stats":
        return cmd_stats(args.sprint)
    return _emit(_state())


if __name__ == "__main__":
    sys.exit(main())
