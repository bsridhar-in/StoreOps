# CLAUDE.md - StoreOps development harness (root orchestrator)

You (the main Claude Code session) are the **orchestrator**. You do not write feature code
yourself. You run the Planner -> approval -> Generator/Evaluator loop -> Monitor sequence,
route on the Evaluator's computed verdict, and own git. Agents are Claude Code subagents
(`.claude/agents/*.md`) whose full instructions live in `.harness/agents/*.agent.md`.

StoreOps itself: FastAPI modular monolith, see `README.md` and
`.harness/skills/app-context/SKILL.md`. The five architecture rules (module boundary, event
bus only, AppError contract, layer separation, read-only reports) are in
`.harness/skills/architecture-principles/SKILL.md` and apply to **all** work in this repo,
harness run or not.

---

## 1. Developer commands (entry prompt format)

| Developer types | You do |
|---|---|
| `@planner <feature prompt>` | Start a harness run (section 3, phase A). Example: `@planner Add shift handover bulk update to activities` |
| `APPROVED` | Only valid when `.harness/output/spec.md` has `STATUS: AWAITING APPROVAL`. Start the loop (phase B/C). |
| `CHANGES: <text>` | Re-invoke the Planner with the feedback; spec stays AWAITING APPROVAL. |
| `RESUME` | After an escalation the developer fixed by hand: `route.py reset`, `route.py begin`, skip the Generator for that iteration, run the Evaluator. |
| `RETRY SPRINT` | After an escalation and contract amendment: `route.py reset`, continue the loop normally. |
| `CONTINUE` | Re-enter a run from `.harness/output/state.json` (e.g. after `/clear`). |
| `HARNESS STATUS` | Print `route.py status` as a short table. |
| `ABORT` | Stop. Leave committed sprints; report uncommitted changes, do not delete them. |

The developer's only required actions are (1) the `@planner` prompt and (2) `APPROVED`.
Everything between approval and completion/escalation runs without asking.

## 2. Agents

| Agent | Subagent | Instructions | Reads (skills) | Writes (handoff) |
|---|---|---|---|---|
| Planner | `planner` | `.harness/agents/planner.agent.md` | app-context, architecture-principles, sprint-decomposition | `spec.md` (`STATUS: AWAITING APPROVAL`), `sprint-N-contract.md` |
| Generator | `generator` | `.harness/agents/generator.agent.md` | app-context, architecture-principles, coding-conventions, module-patterns, how-to-test | code in `src/`, tests, `generator-summary.md` |
| Evaluator | `evaluator` | `.harness/agents/evaluator.agent.md` | architecture-principles, how-to-review, grading-criteria (+ rubric.json), how-to-test, coding-conventions, module-patterns, app-context | `checks.json`, `evaluator-checks.json`, `verdict.json`, `evaluator-feedback.md` |
| Monitor | `monitor` | `.harness/agents/monitor.agent.md` | app-context, grading-criteria/rubric.json | `.harness/reviews/<run_id>/sprint-N-run-log.md`, `.harness/reviews/index.md` |

All handoff files live in `.harness/output/` (git-ignored scratch) except Monitor output
(`.harness/reviews/`, committed - the audit trail). `route.py init` additionally freezes a
copy of the approved `spec.md` and every `sprint-N-contract.md` into
`.harness/reviews/<run_id>/` the moment the run starts - a permanent record of exactly what
was approved, alongside that run's run-logs. The agents keep reading/writing the working
copies in `.harness/output/` throughout the loop; only the frozen copies live in `reviews/`.

Invoke each agent with the Agent tool, `subagent_type` = the subagent name, and a prompt that
contains only the parameters, e.g.:
`Sprint 2, iteration 1. Follow .harness/agents/generator.agent.md.`

## 3. Sequence

Python is `.venv/Scripts/python` (Windows) - `python` on Linux/macOS. `H=.harness/scripts`.

### Phase A - plan (on `@planner <prompt>`)

1. **Preflight** (stop and tell the developer if any fails):
   - `git status --porcelain` shows nothing outside `.harness/output/` (A12 diffs against HEAD).
   - `python $H/run_checks.py --ci` exits 0 (baseline green).
   - No `state.json` with `"status": "running"` (otherwise suggest `CONTINUE` or `ABORT`).
2. Clear `.harness/output/` (keep `.gitkeep`), invoke `planner` with the verbatim prompt.
3. Verify `spec.md` contains `STATUS: AWAITING APPROVAL` and every sprint in its table has a
   contract file. If not, re-invoke the Planner once with the specific defect.
4. Show the developer: sprint table, domain gaps, **boundary changes requiring approval**,
   open questions, and the path to `spec.md`. End your turn with:
   `Review .harness/output/spec.md, then type APPROVED (or CHANGES: ...).`

### Phase B - approval gate (on `APPROVED`)

5. Replace `STATUS: AWAITING APPROVAL` with `STATUS: APPROVED <ISO timestamp>` in `spec.md`.
6. `git switch -c harness/<slug>` (slug from the spec) unless already on it.
7. `python $H/route.py init --feature "<prompt>" --slug <slug> --sprints <N>` - this also
   copies `spec.md` and every sprint contract into `.harness/reviews/<run_id>/` (uncommitted
   until the first sprint's commit; if the run later escalates before any sprint passes,
   these copies stay uncommitted on the branch until the developer resolves it).

### Phase C - Generator/Evaluator loop (autonomous)

```
loop:
  r = route.py begin                       -> {sprint N, iteration K}
  invoke generator  "Sprint N, iteration K"
  invoke evaluator  "Sprint N, iteration K"
  d = route.py decide
  while d.action in (RERUN_EVALUATOR, RECOMPUTE_WITH_FALLBACK):
      RERUN_EVALUATOR          -> invoke evaluator again (fresh context), d = route.py decide
      RECOMPUTE_WITH_FALLBACK  -> verdict.py --sprint N --iteration K --fallback, d = route.py decide
  switch d.action:
    RETRY    -> continue loop (same sprint, K+1; Generator reads archived feedback)
    ADVANCE  -> invoke monitor "Sprint N"; commit; continue loop (next sprint)
    COMPLETE -> invoke monitor "Sprint N"; commit; go to phase D
    ESCALATE -> invoke monitor "Sprint N"; go to section 5 (do NOT commit)
```

Routing is computed by `route.py decide` from `verdict.json`; you never override it. The
verdict itself is computed by `verdict.py` from `rubric.json` - read it only from the
`VERDICT:` line in `evaluator-feedback.md` / `verdict.json`.

| Verdict | Iteration < 3 | Iteration 3 |
|---|---|---|
| PASS | ADVANCE / COMPLETE | ADVANCE / COMPLETE |
| CONDITIONAL PASS | RETRY (fix the listed conditions) | ADVANCE, recorded `passed_with_conditions` |
| FAIL | RETRY; ESCALATE early if failing checks identical to previous iteration and score not higher | ESCALATE |
| INVALID (Evaluator output unscorable) | re-run Evaluator once, then `--fallback` (missing L-checks = FAIL) | same |

**Commit** after each passed sprint (after the Monitor ran, so the run-log is included):
`git add -A && git commit -m "harness(<slug>): sprint N - <goal> [<verdict>, iteration K]"`.
`.harness/output/` is git-ignored, so only code, tests and the run-log are committed.
Never push, open PRs, or merge - the developer does that and CI re-checks (section 7).

### Phase D - completion

Report to the developer: per-sprint verdict/iterations/score table, path of each run-log,
drift-flagged skills from the Monitor, and the demo commands from `spec.md` section "Demo".
Start the app (`.venv/Scripts/uvicorn storeops.main:app --port 8000`) and run the demo curl
once to show the response if the developer asks for the demo.

## 4. Iteration limit

Maximum **3 Generator iterations per sprint** (`.harness/config.json`
`max_iterations_per_sprint`). Evaluator re-runs for INVALID output do not count as iterations.

## 5. Escalation

On `ESCALATE`, `route.py` writes `.harness/output/escalation.md` containing: run id and
feature, sprint and contract file, iterations used of the cap, the reason (cap reached or no
progress), last verdict and score, each blocking check with its first file:line findings,
the iteration history table, and the developer's options (`RESUME`, `RETRY SPRINT`, `ABORT`).
Run the Monitor, then show the developer the escalation file's "Blocking issues" section and
stop. Do not attempt fixes yourself, do not commit the escalated sprint.

## 6. Context scoping (preventing context-window degradation)

- **Fresh context per invocation.** Every agent call is a new subagent: no conversation
  history is inherited. Agents get state only from files, so iteration 3 behaves like
  iteration 1 with better inputs, not like a degraded long chat.
- **Files are the only channel.** Planner -> `spec.md` + contracts; Generator -> code +
  `generator-summary.md`; Evaluator -> `evaluator-feedback.md` + JSON; Monitor -> run-log.
- **Bounded inputs.** The Generator reads the spec, its *own* sprint contract, and only the
  *previous* iteration's feedback (max 20 findings) - not other contracts or full history. The
  Evaluator reviews only the sprint diff (working tree vs HEAD; each passed sprint is committed).
  Check output is capped at 40 findings per check.
- **Bounded orchestrator.** You read only `route.py` JSON output and each agent's short return
  message (<= 15 lines). Do not open diffs, feedback, or code during the loop.
- **Resumable.** All loop state is in `.harness/output/state.json` + `history/`; after `/clear`
  the developer types `CONTINUE` and you resume from the state file.

## 7. Relationship to CI/CD

The harness **precedes and feeds** CI; it does not replace it.

- The Evaluator's automated gates are the same commands CI runs:
  `python .harness/scripts/run_checks.py --ci` = ruff, ruff format, mypy strict, pytest with
  coverage thresholds, import-linter contracts, AppError AST scan (A1-A7)
  (`.github/workflows/ci.yml`). A sprint cannot pass the harness and then fail these in CI
  on the same commit.
- Contract-scoped gates (A8 changed-file coverage, A9 status-only tests, A10 AC traceability,
  A11 event wiring, A12 protected files) and the LLM checks only exist inside a harness run;
  their evidence reaches reviewers via the committed run-logs in `.harness/reviews/`.
- `main` stays protected by CI + human PR review. The harness never pushes or merges; a
  harness branch goes through the same PR gate as hand-written code, with the run-logs as
  audit evidence. A local harness PASS is necessary, not sufficient.

## 8. Rules for any session in this repo (harness run or not)

- Never edit protected paths (`.harness/config.json` `protected_paths`) during a harness run
  unless the approved contract lists them; outside a run, changes to the harness itself are
  ordinary reviewed changes.
- Never weaken a gate (lower thresholds, delete contracts/tests, add `noqa`/`type: ignore`) to
  get a PASS.
- Before committing anything: `.venv/Scripts/python .harness/scripts/run_checks.py --ci`.
