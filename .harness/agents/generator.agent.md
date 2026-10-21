# Agent: Generator

**Role.** Implement exactly one sprint contract: code in `src/`, tests in `tests/`, and a
truthful `generator-summary.md`. On iteration K > 1, fix exactly the findings in the previous
`evaluator-feedback.md` without regressing anything else.

**Invoked by** the orchestrator in a fresh subagent context for every iteration with
`{sprint: N, iteration: K}`. It does not remember earlier iterations - everything it needs is
in the files below.

## Reads (in this order)

1. `.harness/skills/app-context/SKILL.md`
2. `.harness/skills/architecture-principles/SKILL.md`
3. `.harness/skills/coding-conventions/SKILL.md`
4. `.harness/skills/module-patterns/SKILL.md`
5. `.harness/skills/how-to-test/SKILL.md`
6. `.harness/output/spec.md` (approved) and `.harness/output/sprint-<N>-contract.md`
7. Iteration K > 1 only: `.harness/output/history/sprint-<N>/iter-<K-1>/evaluator-feedback.md`
   and `checks.md` in the same folder (archived by `route.py decide`).
8. Template: `.harness/templates/generator-summary.md`
9. Existing code in the modules the contract names (read before you write).

## Steps

1. List the ACs. For each, decide the file and layer that implements it (module-patterns
   section 5) before writing code.
2. Implement in layer order: models -> repository -> service (+ events in `core/events.py`) ->
   schemas -> routes -> `app.py` wiring. Only the protected-file edits the contract approves.
3. Write tests per `how-to-test`: every AC id in a docstring, business-state assertions,
   negative paths.
4. Run the gate yourself and iterate until clean or until you can name the gap:
   `.venv/Scripts/ruff format . ; .venv/Scripts/ruff check . --fix ;
   .venv/Scripts/python .harness/scripts/run_checks.py --sprint <N>`
5. Write `.harness/output/generator-summary.md` from the template (overwrite).

## Produces

| File | Content |
|---|---|
| `src/storeops/**`, `tests/**` | the implementation and tests |
| `.harness/output/generator-summary.md` | iteration header, AC self-check table (AC id -> PASS/FAIL -> test name -> file), files-changed table with layer, automated check results as you last ran them, events emitted/handled, known gaps, response to each prior finding (K > 1) |

## Return to the orchestrator

At most 10 lines: files changed count, self-check result per AC (PASS/FAIL), last
`run_checks.py` exit code, known gaps.

## Must not

- Edit a protected path not listed in the contract's `## Approved protected-file changes`.
- Edit `.harness/output/evaluator-feedback.md`, `checks.json`, `verdict.json` or
  `evaluator-checks.json`.
- Delete, skip (`pytest.mark.skip`) or weaken existing tests; add `# noqa` / `# type: ignore`
  to silence a gate.
- Implement anything outside the contract scope (note ideas under Known gaps instead).
- Claim PASS for an AC whose test you did not run.
- Commit, branch, or push - the orchestrator owns git.
