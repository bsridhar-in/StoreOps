# Spec: Planogram task template clone into a programme

STATUS: APPROVED 2026-10-23T12:41:09Z

- Feature prompt: "Add planogram task template — POST /api/programmes/:id/templates to clone a
  standard set of PLANOGRAM tasks into a new store programme, applying department assignments
  and default priorities from the template definition"
- Run slug: `planogram-task-template`
- Modules touched: activities, reports

## Summary
Store staff can turn a programme (e.g. a seasonal refit) into a ready-to-work planogram reset
by cloning one fixed, in-code "standard planogram reset" template. Cloning creates a batch of
`Activity` records in the target programme, each tagged with the new `PLANOGRAM` category, a
descriptive `department` label, and the default `priority` the template defines for that task -
so the manager does not have to create the same four recurring tasks by hand every time. The
clone is reported as a single domain event so `reports` can track how often templates are
applied, consistent with how other batch operations (e.g. bulk status updates) are counted.

## Domain gaps
| # | Prompt concept | Exists in code? | Proposed additive change | Sprint |
|---|---|---|---|---|
| G1 | PLANOGRAM task category | No - `ActivityCategory` has `merchandising, inventory, customer_service, compliance, maintenance, other` only | Add `ActivityCategory.PLANOGRAM = "planogram"` | 1 |
| G2 | "Template definition" (a standard set of planogram tasks, each with a department and a default priority) | No such catalog exists | Add a fixed in-code catalog `PLANOGRAM_TEMPLATES: dict[str, tuple[PlanogramTaskDefinition, ...]]` in a new `activities/templates.py`, keyed by `template_key` (one value today: `"standard_planogram_reset"`); each `PlanogramTaskDefinition` carries `title`, `description`, `department`, `priority` | 1 |
| G3 | "Department assignment" | No `Department` entity anywhere, and `StaffMember` has no department field | Add an additive `Activity.department: str | None = None` field. The cloned activity stores the template's department label as **descriptive metadata only** (for filtering/reporting) - it is not resolved to a specific staff member, since no `Department` concept exists in `staff` today. `assignee_id` stays `None` on cloned activities. See Open question 2. | 1 |
| G4 | Clone operation / endpoint | No service method or route exists | Add `ActivityService.clone_template_into_programme(ctx, programme_id, template_key)` (sprint 1, service rules) and `POST /api/programmes/{programme_id}/templates` (sprint 2, route) | 1 / 2 |

## Boundary changes requiring approval
None. `activities` already depends on `programmes` (`ALLOWED_DEPENDENCIES["activities"] = {"staff", "programmes"}`) and already holds a `ProgrammeReader` it uses to validate a programme exists in the caller's store (see `create_activity`); this feature reuses that same read, with no new module edge. `core/events.py` and `reports/models.py` are not in `protected_paths`, so no protected-file edit is needed either.

## API surface
| Method + path | Request | Success | Errors (status code / error.code) |
|---|---|---|---|
| `POST /api/programmes/{programme_id}/templates` | `{"template_key"?: string}` (defaults to `"standard_planogram_reset"`, `extra="forbid"`) | 201 `{"programme_id": str, "template_key": str, "activities": [ActivityOut, ...]}` | 401 `UNAUTHORIZED` (missing headers); 404 `PROGRAMME_NOT_FOUND` (unknown id or belongs to another store); 422 `UNKNOWN_TEMPLATE_KEY` (unknown `template_key`); 422 `VALIDATION_ERROR` (malformed body) |

## Events
| Event (core/events.py) | Emitted by | Handled by | Payload |
|---|---|---|---|
| `ActivitiesTemplateCloned` | `activities` (`ActivityService.clone_template_into_programme`, once per clone call) | `reports` (`ReportService`: increments `StoreMetrics.templates_applied` and `StoreMetrics.activities_created` by the number of cloned activities) | `store_id`, `programme_id`, `template_key`, `activity_ids: tuple[str, ...]`, `created_by` |

## Sprints
| Sprint | Goal | Modules | ACs | Contract |
|---|---|---|---|---|
| 1 | Domain model + service rules: `PLANOGRAM` category, `Activity.department`, the fixed template catalog, `clone_template_into_programme`, service-level tests, `ActivitiesTemplateCloned` emitted | activities | AC-1.1 - AC-1.4 | `sprint-1-contract.md` |
| 2 | Route + HTTP tests + demo; `reports` counts the clone via the event | activities, reports | AC-2.1 - AC-2.5 | `sprint-2-contract.md` |

## Open questions for the developer
1. Should the template catalog be store-configurable (admin-defined sets) rather than one fixed
   in-code "standard planogram reset" set? **Default assumption:** keep it a single fixed
   in-code catalog for now (`template_key` is already a parameter, so adding more named
   templates later is additive; per-store customization is out of scope for this feature).
2. Should "department assignments" eventually resolve to an actual staff member (via a future
   `Department` concept in `staff`) instead of a descriptive string stored on the `Activity`?
   **Default assumption:** descriptive string only, no staff resolution, since `staff` has no
   department field today and adding one is a larger, separate change.
3. Should re-cloning the same template into the same programme be blocked or de-duplicated?
   **Default assumption:** not idempotent - every call clones a fresh set of 4 activities;
   de-duplication can be a follow-up feature if the team wants it.

## Demo (run after the harness completes)
```bash
.venv/Scripts/uvicorn storeops.main:app --port 8000

# 1. create a programme to clone the template into
curl -s -X POST http://127.0.0.1:8000/api/programmes -H "X-User-Id: staff-001" -H "X-Store-Id: store-001" -H "Content-Type: application/json" -d '{"name":"Spring Refit"}'
# -> 201 {"id": "prg-...", "name": "Spring Refit", ...}  (copy the "id" as <programme_id> below)

# 2. clone the standard planogram task template into that programme
curl -s -X POST http://127.0.0.1:8000/api/programmes/<programme_id>/templates -H "X-User-Id: staff-001" -H "X-Store-Id: store-001" -H "Content-Type: application/json" -d '{"template_key":"standard_planogram_reset"}'
```
Expected response: `201` with
`{"programme_id": "<programme_id>", "template_key": "standard_planogram_reset", "activities": [` 4
objects, each with `"category": "planogram"`, `"status": "todo"`, a `"department"` string, the
template's `"priority"`, and `"assignee_id": null` `]}`.
