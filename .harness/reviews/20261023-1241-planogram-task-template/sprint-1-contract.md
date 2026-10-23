# Sprint 1 contract: Domain model + service rules for planogram template cloning

- Spec: `.harness/output/spec.md`
- Modules: activities (+ `core/events.py`, not protected)
- Depends on: none

## Scope
- Add `ActivityCategory.PLANOGRAM = "planogram"`.
- Add additive `Activity.department: str | None = None`.
- Add a new file `activities/templates.py` with a `PlanogramTaskDefinition` dataclass
  (`title: str`, `description: str`, `department: str`, `priority: ActivityPriority`) and a
  fixed catalog `PLANOGRAM_TEMPLATES: dict[str, tuple[PlanogramTaskDefinition, ...]]` with one
  key, `"standard_planogram_reset"`, holding exactly 4 task definitions, e.g.:
  1. "Update endcap signage" / department "Merchandising" / priority MEDIUM
  2. "Reset shelf layout - Aisle 1-4" / department "Merchandising" / priority HIGH
  3. "Verify planogram compliance photos uploaded" / department "Compliance" / priority HIGH
  4. "Restock promotional display" / department "Inventory" / priority URGENT
- Add `ActivityService.clone_template_into_programme(ctx, programme_id, template_key) -> list[Activity]`:
  validates the programme exists in `ctx.store_id` (via the existing `ProgrammeReader`),
  validates `template_key`, creates one `Activity` per catalog entry
  (`category=PLANOGRAM`, `status=TODO`, `programme_id=programme_id`, `assignee_id=None`,
  `created_by=ctx.user_id`, `department`/`priority`/`title`/`description` from the catalog
  entry), adds each to the repository, then publishes exactly one `ActivitiesTemplateCloned`
  event for the whole batch.
- Add `ActivitiesTemplateCloned` to `core/events.py`.
- No route yet - this sprint is service-level only.

## Files expected to change
| File | Layer | Change |
|---|---|---|
| `src/storeops/modules/activities/models.py` | model | add `ActivityCategory.PLANOGRAM`; add `Activity.department` |
| `src/storeops/modules/activities/templates.py` | model/data (new file) | `PlanogramTaskDefinition` + `PLANOGRAM_TEMPLATES` catalog |
| `src/storeops/modules/activities/service.py` | service | add `clone_template_into_programme` |
| `src/storeops/core/events.py` | core | add `ActivitiesTemplateCloned` |
| `tests/test_activities_service.py` | test (new file) | service-level tests for AC-1.1 - AC-1.4 |

## Acceptance criteria

### AC-1.1 Clone creates the standard planogram task set
GIVEN programme P exists in store-001 (created via `ProgrammeService.create_programme`) and the
catalog `"standard_planogram_reset"` defines 4 task entries
WHEN `ActivityService.clone_template_into_programme(ctx=ALEX/store-001, programme_id=P, template_key="standard_planogram_reset")` is called
THEN it returns exactly 4 new `Activity` objects, each with `category == ActivityCategory.PLANOGRAM`, `status == ActivityStatus.TODO`, `programme_id == P`, `store_id == "store-001"`, `created_by == ctx.user_id`, `assignee_id is None`, and `department`/`priority` equal to the matching catalog entry (in catalog order)
AND each returned activity is retrievable unchanged via `ActivityRepository.get(activity.id)`
AND exactly one `ActivitiesTemplateCloned` event is published with `programme_id == P`, `template_key == "standard_planogram_reset"`, `activity_ids` equal to the tuple of the 4 created ids (catalog order), `created_by == ctx.user_id`

### AC-1.2 Unknown programme id
GIVEN no programme with id `"prg-missing"` exists
WHEN `ActivityService.clone_template_into_programme(ctx=ALEX/store-001, programme_id="prg-missing", template_key="standard_planogram_reset")` is called
THEN it raises `NotFoundError` with `code == "PROGRAMME_NOT_FOUND"`
AND no `Activity` is added to the repository and no event is published

### AC-1.3 Programme belongs to another store (isolation)
GIVEN programme P2 was created in store-002
WHEN `ActivityService.clone_template_into_programme(ctx=ALEX/store-001, programme_id=P2, template_key="standard_planogram_reset")` is called
THEN it raises `NotFoundError` with `code == "PROGRAMME_NOT_FOUND"` (existence is never revealed across stores)
AND no `Activity` is added and no event is published

### AC-1.4 Unknown template key
GIVEN programme P exists in store-001
WHEN `ActivityService.clone_template_into_programme(ctx=ALEX/store-001, programme_id=P, template_key="does-not-exist")` is called
THEN it raises `ValidationError` with `code == "UNKNOWN_TEMPLATE_KEY"`
AND no `Activity` is added and no event is published

## Events
- EMIT ActivitiesTemplateCloned from activities

## Approved protected-file changes
- None

## Out of scope
- The HTTP route (`POST /api/programmes/{programme_id}/templates`) - sprint 2.
- `reports`/`alerts` handling of `ActivitiesTemplateCloned` - sprint 2 (reports only; no alerts
  subscriber, since cloned activities have no `assignee_id`).
- Per-store/admin-configurable templates, multiple named templates beyond
  `"standard_planogram_reset"`, resolving `department` to an actual staff member, and
  idempotent/de-duplicated re-cloning.
