# Skill: how-to-review (Evaluator)

**Purpose.** The exact review procedure the Evaluator follows so two runs over the same diff
produce the same per-check results. The Evaluator produces evidence and binary results; it
never decides the verdict (`verdict.py` does, from `grading-criteria/rubric.json`).

## 1. Procedure (do the steps in order, do not skip)

1. **Run the automated gates** - never trust the Generator's claims:
   `.venv/Scripts/python .harness/scripts/run_checks.py --sprint <N>` -> `checks.json`, `checks.md`.
   Do not edit, re-run selectively, or reinterpret these results; they are final for A1-A12.
2. **Load scope**: the sprint contract, `generator-summary.md`, and the diff:
   `git status --porcelain` and `git diff` (plus untracked files' full content). Review only
   changed lines and their immediate callers/callees.
3. **Assess each LLM check L1-L12** from the rubric with the questions in section 2.
4. **Write `evaluator-checks.json`** (schema in section 3) - one entry per LLM check, exactly once.
5. **Write `evaluator-feedback.md`** from the template (findings, resolved list, self-check
   comparison). Keep the empty `VERDICT:BEGIN/END` markers; never type a verdict word.
6. **Compute the verdict last**:
   `.venv/Scripts/python .harness/scripts/verdict.py --sprint <N> --iteration <K>` - it fills the
   VERDICT block in `evaluator-feedback.md` and writes `verdict.json`. Exit code 2 = your JSON
   was invalid: fix the JSON structure (not the judgement) and run it again once.

## 2. Binary questions per LLM check (answer YES/NO; NO = FAIL)

| Check | Question (all must be YES for PASS) |
|---|---|
| L1 | For every state change in the diff that affects another module: is it a `self._bus.publish(<Event>(...))` call, after the repository write, and is no other module's service/Reader used to write? |
| L2 | Do changed route handlers contain only: auth dependency, body/query parsing, exactly one service call, response mapping? Do changed repositories contain only storage/query code? |
| L3 | Does no code in `modules/reports` call a mutating method (`add/update/delete/create_*/update_*/bulk_*`) or publish an event that requests another module to change? (N/A -> PASS with evidence "reports not changed": cite `git status`.) |
| L4 | Does every new `raise` use the class in the `architecture-principles` R3 table matching the situation, with a SCREAMING_SNAKE domain code, and is other-store access a 404? |
| L5 | Are new services/subscribers constructed and registered only in `app.py`, and do cross-module reads use an exported `<Name>Reader` Protocol? Do any protected-file edits match the approved spec text exactly? |
| L6 | For each AC: is there a test (found via its AC id) whose assertions check the THEN clause's business state? Would that test fail if the new service branch were deleted? |
| L7 | Are the negative paths from `how-to-test` section 4 that apply to this sprint each tested with an exact error code? |
| L8 | Is every row of the generator-summary AC table that says PASS backed by the cited test, and does every changed file appear in the files table with its correct layer? |
| L9 | Is every AC implemented, and is there no endpoint, field, or behaviour that no AC asks for? |
| L10 | Do new schemas use `extra="forbid"` (requests) / `from_attributes=True` (responses), `*Create/*Update/*Request/*Out` names, StrEnum lowercase values, `utcnow()`/`new_id()`, and store scoping on every query? |
| L11 | Is every new repository a Protocol + `InMemory*` pair with the service typed against the Protocol? (No new repository -> PASS, cite the diff.) |
| L12 | Is the diff free of `print`, commented-out code, unused helpers, and TODOs not listed in Known gaps? |

## 3. `evaluator-checks.json` schema

```json
{
  "sprint": 1,
  "iteration": 2,
  "checks": [
    {
      "id": "L1",
      "result": "FAIL",
      "reason": "bulk_update_status writes alerts directly",
      "evidence": [
        {"file": "src/storeops/modules/activities/service.py", "line": 141,
         "quote": "self._alerts.add(Alert(...))", "fix": "publish ActivitiesBulkUpdated; let AlertService subscribe"}
      ]
    }
  ]
}
```

## 4. Handling variability (how a judgement becomes a stable binary)

- **Evidence or fail.** Every result (PASS *and* FAIL) cites at least one `file` + `line`
  (+ short `quote`). `verdict.py` converts an evidence-less PASS into FAIL. This stops
  "looks fine" passes.
- **Questions, not impressions.** Answer the section-2 question literally. Style preferences
  that are not in a skill file are not failures - mention them under "Observations" only.
- **Doubt resolves to FAIL with a specific fix.** If you cannot confirm YES from the code,
  the answer is NO; the `fix` field must say what evidence would make it YES. A
  wrongly-failed check costs one iteration; a wrongly-passed one reaches main.
- **Automated beats LLM.** Never mark an L-check FAIL for something an A-check already
  covers and passed (e.g. import cycles), and never PASS L1 when A5 `R2-*` is BROKEN.
- **Same finding, same check.** A finding belongs to the single check whose question it
  answers; do not double-penalise.
- **Re-review on iteration K>1**: first confirm each finding of iteration K-1
  (`.harness/output/history/sprint-N/iter-(K-1)/evaluator-feedback.md`) is resolved; a
  previously passed check is re-assessed only if its files changed.
- **Fallback when your own output is ambiguous**: if `verdict.py` returns INVALID twice, the
  orchestrator runs it with `--fallback`, scoring every missing/invalid L-check as FAIL.

## 5. Feedback quality for the Generator

Each FAIL bullet in `evaluator-feedback.md` is: `` `path:line` `` - check id - what is wrong -
the concrete fix (name the class/method/event to use). Order: hard-gate failures first, then
major, then minor. Max 20 bullets; group repeated findings.
