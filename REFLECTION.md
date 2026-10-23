# Reflection

Based on three real harness runs (shift-handover-bulk-status, regional-rollup-report,
planogram-task-template — 8 sprints, 8 commits) and one deliberately adversarial probe run,
not on the design intent alone.

## What it did well

**The gates caught exactly what they were built to catch, with evidence.** A probe planted a
direct cross-module repository import, two raw raises, a status-only test, an undefined
event, and an unapproved protected-file edit. `A1`–`A12` caught every one of them with a
file:line citation, and `verdict.py` turned that into the same FAIL verdict (12.2/100) every
time it was recomputed — no run-to-run disagreement about whether the sprint passed.

**File-based handoff survived real interruptions.** Across 8 sprints, each Generator/Evaluator
pair ran as a fresh subagent with zero shared memory, often separated by other work in between.
Not one iteration lost context it needed — the previous iteration's feedback, the contract, the
approved spec were all exactly where the agent file said they'd be.

**Independent, narrowly-scoped features merged cleanly.** `planogram-task-template` was a clean
fast-forward into `master` — two sprints, no overlap with anything else, no conflict.

**The retention fix, once correct, worked on a real run.** `spec.md`, both sprint contracts, and
every iteration's `generator-summary.md`/`evaluator-feedback.md` landed in
`.harness/reviews/20261023-1241-planogram-task-template/` and were verified present in the
commit — not just in a disposable test.

## Where it fell short

**I broke the thing I was asked to fix, while fixing it.** Verifying the new retention code
against the *live* `.harness/output/` scratch directory overwrote and then deleted the real
`spec.md`/contracts for two already-completed runs — the exact artifacts the user had just
asked to preserve. The harness had no safeguard distinguishing "scratch I can freely smoke-test
against" from "scratch that happens to hold the only copy of something irreplaceable right
now." That's a process gap in how the harness's own tooling gets developed, not in the harness's
logic.

**Three sibling runs collided hard at merge time, with no warning beforehand.** All three
feature branches were planned and built against whatever `master` looked like when each run
started, with zero awareness of the other two in flight. Two of the three merges needed 10
hand-resolved conflicts across the exact files every StoreOps feature touches
(`activities/service.py`, `models.py`, `__init__.py`, `schemas.py`, `routes.py`,
`reports/service.py`). The harness enforces architecture boundaries rigorously but has no
concept of *other harness runs* at all.

**The retry/escalation path is designed but practically unexercised.** All 8 real sprints
passed on iteration 1 at 100/100. That's either a genuinely strong Generator, or a rubric that
first-pass Generator output clears easily, or both — the design has never actually been tested
by a real, organically imperfect Generator attempt. The only FAIL/escalation path exercised in
this build was a synthetic probe I planted on purpose, not a real sprint that needed a second
try.

## One concrete improvement

**Add a pre-plan collision check**, run by the orchestrator in Phase A before invoking the
Planner: list every other local `harness/*` branch not yet merged into `master`, diff each
against its own merge-base to get its changed-file set, and if any file overlaps with the
*current* feature's likely scope (the modules named in the developer's prompt, cross-checked
against `app-context`'s module map), show the developer that overlap — branch name, files,
sprint — before approval, not at merge time. This is a few lines on top of `git diff --name-only
<merge-base>..<branch>` for each sibling branch, already exactly what I ran by hand after the
third run was built, three sprints too late to matter. Surfacing it at Phase A would have let
the developer choose, up front, to either sequence the two features or explicitly accept the
merge cost — rather than discovering a 10-conflict integration only after all the work on both
sides was already done.
