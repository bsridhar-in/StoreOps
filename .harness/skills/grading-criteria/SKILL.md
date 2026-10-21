# Skill: grading-criteria (Evaluator; Monitor uses it to map failures to skills)

**Purpose.** The graded evaluation framework: three weighted dimensions, their hard gates,
the checklist with pass/fail criteria, and the deterministic rule that turns check results
into PASS / CONDITIONAL PASS / FAIL. The machine-readable source of truth is
[`rubric.json`](rubric.json) in this folder; `verdict.py` reads it. This page explains it.

## 1. Dimensions and weights (sum = 100%)

| Dim | Name | Weight | Hard gates (automated) | Hard gates (LLM, binary) |
|---|---|---|---|---|
| D1 | Architecture compliance | **40%** | A5 import-linter, A6 error contract, A11 event wiring, A12 protected files | L1 event bus, L3 read-only reports |
| D2 | Functional correctness and test quality | **35%** | A4 pytest, A7 coverage, A8 changed-file coverage, A9 status-only tests, A10 AC traceability | L6 THEN clauses asserted |
| D3 | Code quality and conventions | **25%** | A1 ruff, A2 ruff format, A3 mypy strict | - |

Every dimension has at least one hard gate backed by a deterministic tool.

## 2. Checklist

Points are per dimension (each dimension totals 100). Severity: **hard** = any FAIL makes the
verdict FAIL; **major** = blocks PASS (max CONDITIONAL PASS); **minor** = only costs points.

### D1 Architecture compliance (40%)

| Id | Pts | Sev | PASS when | Tool / owner skill |
|---|---|---|---|---|
| A5 | 20 | hard | `lint-imports` exit 0: all `R1-*`, `R2-*`, `R4-*`, `core-independence` contracts KEPT | import-linter / architecture-principles |
| A6 | 15 | hard | zero `raise <builtin>` / `HTTPException` in any service or routes file | AST scan / coding-conventions |
| A11 | 10 | hard | each contract `EMIT`/`HANDLE` line: event class in `core/events.py`, `.publish(Event(` in emitter, `.subscribe(Event,` in handler | text scan / module-patterns |
| A12 | 10 | hard | no protected path changed unless listed in contract `## Approved protected-file changes` | git status / architecture-principles |
| L1 | 15 | hard | how-to-review L1 question YES | LLM / module-patterns |
| L2 | 10 | major | L2 question YES | LLM / module-patterns |
| L3 | 10 | hard | L3 question YES | LLM / architecture-principles |
| L4 | 10 | major | L4 question YES | LLM / coding-conventions |
| L5 | 10 | minor | L5 question YES | LLM / module-patterns |

### D2 Functional correctness and test quality (35%)

| Id | Pts | Sev | PASS when | Tool / owner skill |
|---|---|---|---|---|
| A4 | 20 | hard | full `pytest` suite exit 0 | pytest / how-to-test |
| A7 | 10 | hard | service >= 80, routes >= 70, core >= 60, overall >= 70 (% lines) | coverage.py / how-to-test |
| A8 | 10 | hard | each changed source file >= its scope threshold | coverage.py / how-to-test |
| A9 | 10 | hard | no changed `test_*` function with only `status_code` assertions | AST scan / how-to-test |
| A10 | 10 | hard | every `AC-N.M` of the contract appears in `tests/` | text scan / how-to-test |
| L6 | 20 | hard | L6 question YES for every AC | LLM / how-to-test |
| L7 | 10 | major | L7 question YES | LLM / how-to-test |
| L8 | 5 | major | L8 question YES | LLM / how-to-review |
| L9 | 5 | major | L9 question YES | LLM / sprint-decomposition |

### D3 Code quality and conventions (25%)

| Id | Pts | Sev | PASS when | Tool / owner skill |
|---|---|---|---|---|
| A1 | 20 | hard | `ruff check .` exit 0 | ruff / coding-conventions |
| A2 | 10 | hard | `ruff format --check .` exit 0 | ruff / coding-conventions |
| A3 | 25 | hard | `mypy` (strict, pydantic plugin) exit 0 | mypy / coding-conventions |
| L10 | 25 | major | L10 question YES | LLM / coding-conventions |
| L11 | 10 | minor | L11 question YES | LLM / module-patterns |
| L12 | 10 | minor | L12 question YES | LLM / coding-conventions |

## 3. Verdict rule (deterministic - implemented in `verdict.py`)

```
dimension_score = 100 * points_of_passed_checks / 100
score           = 0.40*D1 + 0.35*D2 + 0.25*D3          (rounded to 0.1)

if any hard check FAILED or score < 75     -> FAIL
elif score >= 90 and no major check FAILED -> PASS
else                                       -> CONDITIONAL PASS
```

Given the same per-check results the verdict is always the same. The only non-deterministic
inputs are the L-checks, constrained by evidence-or-fail and binary questions
(`how-to-review` section 4).

## 4. Converting variable LLM output into stable results

| Source of variability | Control |
|---|---|
| Generated code differs run to run | Automated gates judge outcomes (contracts kept, tests pass), not code shape |
| Evaluator leniency | Hard gates are tools; LLM PASS requires file:line evidence or is scored FAIL |
| Evaluator vagueness | Each L-check is one YES/NO question; severity fixed in rubric, not chosen by the Evaluator |
| Malformed Evaluator output | `verdict.py` validates the JSON -> INVALID -> one re-run of the Evaluator in a fresh context -> then `--fallback` (missing = FAIL) |
| Flip-flopping across iterations | Iteration K first re-verifies K-1 findings; route.py escalates when the same failing set repeats with no score gain |

## 5. Routing per verdict (executed by `route.py decide`)

| Verdict | Iterations < 3 | Iteration = 3 |
|---|---|---|
| PASS | Monitor -> commit -> next sprint | same |
| CONDITIONAL PASS | RETRY with the major/minor findings | accept as `passed_with_conditions`, conditions recorded in run-log, advance |
| FAIL | RETRY (or ESCALATE early if no progress) | ESCALATE -> `.harness/output/escalation.md` |
