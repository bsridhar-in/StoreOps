# Generator summary - sprint 2, iteration 1

## AC self-check
| AC | Self-check | Test(s) proving it | Implemented in |
|---|---|---|---|
| AC-2.1 | PASS | `tests/test_activities_api.py::test_clone_template_creates_four_planogram_activities` | `src/storeops/modules/activities/routes.py::clone_template_into_programme` |
| AC-2.2 | PASS | `tests/test_activities_api.py::test_clone_template_into_other_store_programme_is_not_found` | `src/storeops/modules/activities/service.py::ActivityService.clone_template_into_programme` |
| AC-2.3 | PASS | `tests/test_activities_api.py::test_clone_template_requires_authentication` | `src/storeops/core/auth.py` (via `Auth` dependency on the new route) |
| AC-2.4 | PASS | `tests/test_activities_api.py::test_clone_template_rejects_unknown_template_key` | `src/storeops/modules/activities/service.py::ActivityService.clone_template_into_programme` |
| AC-2.5 | PASS | `tests/test_activities_api.py::test_clone_template_increments_report_metrics` | `src/storeops/modules/reports/service.py::ReportService._on_activities_template_cloned` |

## Files changed
| File | Layer | Change |
|---|---|---|
| `src/storeops/modules/activities/schemas.py` | schema | added `TemplateCloneRequest`, `TemplateCloneOut`; added `department: str \| None` to `ActivityOut` |
| `src/storeops/modules/activities/routes.py` | route | new `templates_router` with `POST /api/programmes/{programme_id}/templates`, status 201 |
| `src/storeops/modules/activities/__init__.py` | public API | exported `templates_router` |
| `src/storeops/app.py` | composition root | included `activities.templates_router` alongside `activities.router` |
| `src/storeops/modules/reports/models.py` | model | added `StoreMetrics.templates_applied: int = 0` |
| `src/storeops/modules/reports/service.py` | service | subscribed to `ActivitiesTemplateCloned`; `_on_activities_template_cloned` increments `templates_applied` by 1 and `activities_created` by `len(event.activity_ids)` |
| `tests/test_activities_api.py` | test | 5 new HTTP tests for AC-2.1 - AC-2.5; strengthened 3 pre-existing status-only tests in the same file (`test_list_rejects_unknown_status_filter`, `test_owner_can_delete`, `test_store_manager_can_delete`) with business assertions (error code / follow-up read) to satisfy A9 on the whole changed file, without altering their original intent |

## Events
| Event | Emitted where | Handled where |
|---|---|---|
| `ActivitiesTemplateCloned` | `activities/service.py::ActivityService.clone_template_into_programme` (sprint 1, unchanged) | `reports/service.py::ReportService._on_activities_template_cloned` (new, sprint 2) |

## Automated checks (last local run of `run_checks.py --sprint 2`)
| Check | Status |
|---|---|
| A1 | PASS - ruff check: clean |
| A2 | PASS - ruff format: clean |
| A3 | PASS - mypy --strict: clean |
| A4 | PASS - pytest: 64 passed |
| A5 | PASS - import-linter: 11 kept, 0 broken |
| A6 | PASS - error contract: 0 raw raise(s) in service/routes |
| A7 | PASS - coverage: service 99.0% (min 80), routes 94.7% (min 70), shared 98.6% (min 60), overall 98.5% (min 70) |
| A8 | PASS - changed-file coverage: 6 file(s) checked |
| A9 | PASS - assertion quality: 1 changed test file(s), 0 status-only test(s) |
| A10 | PASS - AC traceability: 5/5 ACs referenced |
| A11 | PASS - event wiring: 0 EMIT, 1 HANDLE, 0 missing |
| A12 | PASS - protected files: 0 unapproved; approved = none |

Also ran `.venv/Scripts/python .harness/scripts/run_checks.py --ci`: A1-A7 all PASS (A8-A12
correctly SKIPPED in CI mode).

## Response to previous feedback (iteration > 1)
N/A - this is iteration 1.

## Known gaps
None. All 5 ACs implemented and self-checked PASS; no protected-file edits were needed (none
were approved in the contract and none were made).
