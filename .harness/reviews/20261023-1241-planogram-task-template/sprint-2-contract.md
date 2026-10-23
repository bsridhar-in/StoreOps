# Sprint 2 contract: Route, demo, and reports counting for template cloning

- Spec: `.harness/output/spec.md`
- Modules: activities, reports
- Depends on: sprint 1

## Scope
- Add Pydantic schemas `TemplateCloneRequest` (`template_key: str = "standard_planogram_reset"`,
  `extra="forbid"`) and `TemplateCloneOut` (`programme_id: str`, `template_key: str`,
  `activities: list[ActivityOut]`) in `activities/schemas.py`; add `department: str | None` to
  `ActivityOut`.
- Add a second router in `activities/routes.py` (no `/api/activities` prefix) exposing
  `POST /api/programmes/{programme_id}/templates`, calling
  `ActivityService.clone_template_into_programme` and returning `TemplateCloneOut` with status
  201. Export it from `activities/__init__.py`; include it in `app.py` alongside the existing
  `activities.router`.
- `ReportService.register` subscribes to `ActivitiesTemplateCloned`: increments
  `StoreMetrics.templates_applied` by 1 and `StoreMetrics.activities_created` by
  `len(event.activity_ids)`.
- Add `StoreMetrics.templates_applied: int = 0` to `reports/models.py`.
- HTTP tests (AC-2.1 - AC-2.5) and the spec's demo curl commands must work against the running
  app.

## Files expected to change
| File | Layer | Change |
|---|---|---|
| `src/storeops/modules/activities/schemas.py` | schema | `TemplateCloneRequest`, `TemplateCloneOut`; add `department` to `ActivityOut` |
| `src/storeops/modules/activities/routes.py` | route | new router, `POST /api/programmes/{programme_id}/templates` |
| `src/storeops/modules/activities/__init__.py` | public API | export the new router |
| `src/storeops/app.py` | composition root | include the new router |
| `src/storeops/modules/reports/models.py` | model | add `StoreMetrics.templates_applied` |
| `src/storeops/modules/reports/service.py` | service | subscribe to `ActivitiesTemplateCloned`, update counters |
| `tests/test_activities_api.py` | test | HTTP tests for AC-2.1 - AC-2.5 |

## Acceptance criteria

### AC-2.1 Happy path clones and persists
GIVEN MANAGER creates a programme `POST /api/programmes {"name": "Spring Refit"}` in store-001
WHEN ALEX sends `POST /api/programmes/{programme_id}/templates` with body `{}` (no
`template_key`, so it defaults)
THEN the response is 201 with body `{"programme_id": "<programme_id>", "template_key": "standard_planogram_reset", "activities": [...]}` containing exactly 4 items, each with `"category": "planogram"`, `"status": "todo"`, a non-null `"department"`, the catalog's `"priority"`, and `"assignee_id": null`
AND `GET /api/activities?programme_id=<programme_id>` (ALEX) returns those same 4 activities

### AC-2.2 Programme in another store is not found
GIVEN OTHER_STORE creates a programme `POST /api/programmes {"name": "Other"}` in store-002
WHEN ALEX (store-001) sends `POST /api/programmes/{other_programme_id}/templates {}`
THEN the response is 404 with `error.code == "PROGRAMME_NOT_FOUND"`
AND `GET /api/activities` (ALEX) still returns no planogram tasks from this attempt

### AC-2.3 Missing auth headers
WHEN a request is sent with no auth headers to `POST /api/programmes/{any_id}/templates {}`
THEN the response is 401 with `error.code == "UNAUTHORIZED"`

### AC-2.4 Unknown template key
GIVEN programme P exists in store-001
WHEN ALEX sends `POST /api/programmes/{P}/templates {"template_key": "bogus"}`
THEN the response is 422 with `error.code == "UNKNOWN_TEMPLATE_KEY"`

### AC-2.5 Reports counts the clone
GIVEN programme P exists in store-001 and (via the `app` fixture) `app.state.report_service.get_store_metrics("store-001").templates_applied == 0`
WHEN ALEX sends `POST /api/programmes/{P}/templates {}` and the response is 201
THEN `app.state.report_service.get_store_metrics("store-001").templates_applied == 1` and
`activities_created` increased by exactly 4 from its value before the call
AND sending a second `POST /api/programmes/{P}/templates {}` raises `templates_applied` to `2`

## Events
- HANDLE ActivitiesTemplateCloned in reports

## Approved protected-file changes
- None

## Out of scope
- `alerts` handling of `ActivitiesTemplateCloned` (cloned activities have no `assignee_id`, so
  there is nobody to notify).
- A public `GET /api/reports/...` endpoint - `templates_applied` is only checked via
  `app.state.report_service` in tests, consistent with reports having no public endpoints today.
- Including `templates_applied` in `RegionMetrics`/region rollups.
- Idempotent/de-duplicated re-cloning (out of scope per spec Open question 3).
