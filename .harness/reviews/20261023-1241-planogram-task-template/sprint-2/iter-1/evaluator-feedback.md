# Evaluator feedback - sprint 2, iteration 1

<!-- VERDICT:BEGIN -->
VERDICT: PASS
SCORE: 100.0 / 100
HARD GATES FAILED: none

| Dimension | Weight | Score |
|---|---|---|
| D1 Architecture compliance | 40% | 100.0 |
| D2 Functional correctness and test quality | 35% | 100.0 |
| D3 Code quality and conventions | 25% | 100.0 |

| Check | Severity | Result | Reason |
|---|---|---|---|
| A5 | hard | PASS | import-linter: Contracts: 11 kept, 0 broken. |
| A6 | hard | PASS | error contract: 0 raw raise(s) in service/routes |
| A11 | hard | PASS | event wiring: 0 EMIT, 1 HANDLE, 0 missing |
| A12 | hard | PASS | protected files: 0 unapproved; approved = none |
| L1 | hard | PASS | reports reacts to ActivitiesTemplateCloned via bus.subscribe and only writes its own repository; no direct cross-module service call |
| L2 | major | PASS | new route handler only parses body/path, takes ctx, calls exactly one service method, and maps the result to the response model |
| L3 | hard | PASS | the only reports change is _on_activities_template_cloned, which calls self.get_store_metrics (own reader) and self._repo.save (own repository); no mutating call into activities/programmes/staff and no event published back |
| L4 | major | PASS | no new `raise` statement is added in this diff; the route/service code paths exercised by the new endpoint reuse sprint-1 raises (NotFoundError/PROGRAMME_NOT_FOUND, ValidationError/UNKNOWN_TEMPLATE_KEY) which are out of scope for this sprint's diff |
| L5 | minor | PASS | the new router is wired only in app.py (added to the router tuple); no new service/subscriber is constructed outside app.py; reports already held its own ReportService instance and only gained one more bus.subscribe line inside the existing register() method; no new cross-module Reader was introduced |
| A4 | hard | PASS | pytest: 64 passed in 2.32s |
| A7 | hard | PASS | coverage: service 99.0% (min 80), routes 94.7% (min 70), shared 98.6% (min 60), overall 98.5% (min 70) |
| A8 | hard | PASS | changed-file coverage: 6 file(s) checked |
| A9 | hard | PASS | assertion quality: 1 changed test file(s), 0 status-only test(s) |
| A10 | hard | PASS | AC traceability: 5/5 ACs referenced |
| L6 | hard | PASS | each AC's THEN clause is asserted on business state, not just status code |
| L7 | major | PASS | no-auth (AC-2.3), other-store isolation (AC-2.2), and invalid body/enum (AC-2.4) are each tested with an exact error code; no permission rule or partial-failure case applies to this single-shot clone endpoint |
| L8 | major | PASS | every AC row in generator-summary.md cites a test that exists verbatim in tests/test_activities_api.py, and the files table lists the correct layer for each changed file |
| L9 | major | PASS | implementation covers exactly the contract scope: TemplateCloneRequest/Out, department field, new router, reports counters; no alerts handling, no public reports endpoint, no RegionMetrics change was added, matching 'Out of scope' |
| A1 | hard | PASS | ruff check: clean |
| A2 | hard | PASS | ruff format: clean |
| A3 | hard | PASS | mypy --strict: clean |
| L10 | major | PASS | TemplateCloneRequest uses extra=forbid, TemplateCloneOut uses from_attributes=True, both follow *Request/*Out naming; new StoreMetrics field defaults to 0 like its siblings; reports handler scopes by event.store_id for every lookup/save |
| L11 | minor | PASS | no new repository is introduced in this diff (reports/models.py and reports/service.py only; repository.py untouched) |
| L12 | minor | PASS | no print/commented-out code/unlisted TODO in the diff; the only unlisted-but-notable change is strengthening 3 pre-existing status-only tests to satisfy A9, which the generator-summary discloses and is not a hygiene violation |
<!-- VERDICT:END -->

## Blocking findings (hard gates, then major)
None.

## Minor findings
None.

## Previous findings resolved (iteration > 1)
N/A - this is iteration 1.

## Generator self-check vs evaluation
| AC | Generator said | Evaluator found | Evidence |
|---|---|---|---|
| AC-2.1 | PASS | Confirmed - 201, 4 planogram activities with department/priority set, GET matches | `tests/test_activities_api.py::test_clone_template_creates_four_planogram_activities` |
| AC-2.2 | PASS | Confirmed - 404 PROGRAMME_NOT_FOUND, no planogram activities leaked into ALEX's store | `tests/test_activities_api.py::test_clone_template_into_other_store_programme_is_not_found` |
| AC-2.3 | PASS | Confirmed - 401 UNAUTHORIZED with no headers | `tests/test_activities_api.py::test_clone_template_requires_authentication` |
| AC-2.4 | PASS | Confirmed - 422 UNKNOWN_TEMPLATE_KEY | `tests/test_activities_api.py::test_clone_template_rejects_unknown_template_key` |
| AC-2.5 | PASS | Confirmed - templates_applied 0 -> 1 -> 2, activities_created +4 per clone | `tests/test_activities_api.py::test_clone_template_increments_report_metrics` |

## Observations (not scored)
- Generator also strengthened three pre-existing status-only tests
  (`test_list_rejects_unknown_status_filter`, `test_owner_can_delete`,
  `test_store_manager_can_delete`) to add business assertions, keeping A9 clean on the whole
  changed test file without altering their original intent - reasonable incidental cleanup,
  disclosed in generator-summary.md.
- All 12 automated gates (A1-A12) passed with no exceptions; no protected files touched.
