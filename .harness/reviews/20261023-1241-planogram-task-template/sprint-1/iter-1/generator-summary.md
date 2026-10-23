# Generator summary - sprint 1, iteration 1

## AC self-check
| AC | Self-check | Test(s) proving it | Implemented in |
|---|---|---|---|
| AC-1.1 | PASS | `tests/test_activities_service.py::test_clone_creates_the_standard_planogram_task_set` | `src/storeops/modules/activities/service.py::ActivityService.clone_template_into_programme` |
| AC-1.2 | PASS | `tests/test_activities_service.py::test_clone_rejects_unknown_programme_id` | `src/storeops/modules/activities/service.py::ActivityService.clone_template_into_programme` |
| AC-1.3 | PASS | `tests/test_activities_service.py::test_clone_rejects_programme_from_another_store` | `src/storeops/modules/activities/service.py::ActivityService.clone_template_into_programme` |
| AC-1.4 | PASS | `tests/test_activities_service.py::test_clone_rejects_unknown_template_key` | `src/storeops/modules/activities/service.py::ActivityService.clone_template_into_programme` |

## Files changed
| File | Layer | Change |
|---|---|---|
| `src/storeops/modules/activities/models.py` | model | added `ActivityCategory.PLANOGRAM = "planogram"`; added additive `Activity.department: str \| None = None` |
| `src/storeops/modules/activities/templates.py` (new) | model/data | `PlanogramTaskDefinition` dataclass + fixed `PLANOGRAM_TEMPLATES` catalog with one key `"standard_planogram_reset"` (4 task definitions, as specified in the contract) |
| `src/storeops/modules/activities/service.py` | service | added `ActivityService.clone_template_into_programme(ctx, programme_id, template_key)`: validates the programme exists in `ctx.store_id` via `ProgrammeReader.exists_in_store`, validates `template_key` against `PLANOGRAM_TEMPLATES`, creates one `Activity` per catalog entry (category `PLANOGRAM`, status `TODO`, `assignee_id=None`), adds each to the repository, publishes one `ActivitiesTemplateCloned` event for the batch |
| `src/storeops/core/events.py` | shared | added `ActivitiesTemplateCloned(DomainEvent)` with `programme_id`, `template_key`, `activity_ids: tuple[str, ...]`, `created_by` |
| `tests/test_activities_service.py` (new) | test | service-level tests for AC-1.1 - AC-1.4, using real `ProgrammeService`/`StaffService` with `InMemory*` repositories and a real `EventBus` |

## Events
| Event | Emitted where | Handled where |
|---|---|---|
| `ActivitiesTemplateCloned` | `ActivityService.clone_template_into_programme` (once per call, after all activities are added) | none yet - `reports` subscription is sprint 2 scope |

## Automated checks (last local run of `run_checks.py --sprint 1`)
| Check | Status | Summary |
|---|---|---|
| A1 | PASS | ruff check: clean |
| A2 | PASS | ruff format: clean |
| A3 | PASS | mypy --strict: clean |
| A4 | PASS | pytest: 59 passed |
| A5 | PASS | import-linter: Contracts: 11 kept, 0 broken |
| A6 | PASS | error contract: 0 raw raise(s) in service/routes |
| A7 | PASS | coverage: service 99.0% (min 80), routes 94.4% (min 70), shared 98.6% (min 60), overall 98.5% (min 70) |
| A8 | PASS | changed-file coverage: 4 file(s) checked |
| A9 | PASS | assertion quality: 1 changed test file(s), 0 status-only test(s) |
| A10 | PASS | AC traceability: 4/4 ACs referenced |
| A11 | PASS | event wiring: 1 EMIT, 0 HANDLE, 0 missing |
| A12 | PASS | protected files: 0 unapproved; approved = none |

## Response to previous feedback (iteration > 1)
N/A - iteration 1.

## Known gaps
None. Route (`POST /api/programmes/{programme_id}/templates`) and `reports` handling of
`ActivitiesTemplateCloned` are out of scope for this sprint per the contract (sprint 2).
