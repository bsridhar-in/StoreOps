# Skill: sprint-decomposition (Planner)

**Purpose.** How the Planner turns one feature prompt into `spec.md` plus sprint contracts
that a Generator can implement in at most three iterations and an Evaluator can grade
mechanically.

## 1. Sizing rules

- 1 to 4 sprints per feature. A sprint is one vertical, independently passing slice: it must
  leave `run_checks.py --sprint N` green on its own.
- A sprint touches at most **2 modules** plus `core/events.py` / `core/errors.py` / `app.py`.
- 3 to 8 acceptance criteria per sprint. More than 8 -> split.
- Order: (1) model + repository + service rules with service-level tests, (2) route +
  HTTP tests + demo, (3) cross-module side effects via events, (4) reports/rollups. Collapse
  steps when the feature is small; never put an event subscriber before the event exists.
- Every boundary change (see `architecture-principles`, "Changing a boundary") goes in the
  **first** sprint that needs it and is listed in that contract's
  `## Approved protected-file changes`.

## 2. Acceptance criteria format (machine-checked)

IDs are `AC-<sprint>.<n>`, unique, sequential. A10 requires every id to be referenced by a
test. Each AC is GIVEN / WHEN / THEN with **observable business state** in THEN:

```
### AC-1.3 Partial failure keeps successful updates
GIVEN activities A (todo) and B (todo) in store-001 and an id C that belongs to store-002
WHEN ALEX sends PATCH /api/activities/bulk-status {"ids":[A,B,C],"status":"done"}
THEN the response is 207 with results A=updated, B=updated, C=failed code ACTIVITY_NOT_FOUND
AND  GET /api/activities/A returns status "done" and C is unchanged in store-002
AND  one ActivitiesBulkUpdated event is published listing exactly [A, B]
```

Bad THEN clauses (rejected by L6/L9): "returns 200", "works correctly", "handles errors".

Every sprint must include at least one AC for each that applies:
- the happy path with persisted state checked by a follow-up read;
- store isolation (other store -> 404 `<THING>_NOT_FOUND`);
- auth (missing headers -> 401) for any new endpoint;
- validation (422 with the exact `code`);
- permission (403 with the exact `code`) if the feature restricts who may act;
- the event emitted (and the subscriber effect, e.g. an alert visible via `GET /api/alerts`).

## 3. Events and protected files - contract syntax

```
## Events
- EMIT ActivitiesBulkUpdated from activities
- HANDLE ActivitiesBulkUpdated in reports

## Approved protected-file changes
- tests/test_architecture.py   (ALLOWED_DEPENDENCIES: reports -> {"activities"}, spec item B1)
```

Write `- None` when there are none. These lines are parsed by `harness_common.py`; keep the
exact `- EMIT X from y` / `- HANDLE X in y` shapes.

## 4. Vocabulary

Use code names from `app-context` section 5 (Activity, not Task; `urgent`, not CRITICAL).
When the prompt needs a concept that does not exist (Department Lead role, due dates,
regions, Report record, PLANOGRAM category), add a "Domain gaps" entry in `spec.md` with the
proposed additive change, and make the change an explicit AC.

## 5. Worked decomposition - "Add shift handover bulk update"

- Domain gaps: none required (DONE/BLOCKED exist). Audit entry is new -> owned by
  `activities` (`ActivityAuditEntry` dataclass + `InMemoryActivityAuditRepository`).
- Sprint 1 - service + repository: `ActivityService.bulk_update_status(ctx, ids, status, note)`;
  per-id result (updated / failed + code); allowed target statuses only DONE/BLOCKED (422
  `INVALID_BULK_STATUS`); max 100 ids (422 `BULK_LIMIT_EXCEEDED`); duplicate ids collapsed;
  audit entry per updated activity (who, from, to, at). Events: EMIT `ActivitiesBulkUpdated`.
- Sprint 2 - route + HTTP tests + demo: `PATCH /api/activities/bulk-status` (must be declared
  **before** `/{activity_id}` routes), 200 when all succeed, 207 when some failed, 401, 422.
  HANDLE `ActivitiesBulkUpdated in reports` (completion counters) and `in alerts` (assignee
  notified when someone else changed status).

## 6. Self-check before writing `STATUS: AWAITING APPROVAL`

- [ ] Every AC has an id, GIVEN/WHEN/THEN and observable state in THEN.
- [ ] Each sprint has happy, isolation, auth, validation ACs where applicable.
- [ ] Every cross-module effect is an event in `## Events`.
- [ ] Every protected-file change is listed in the spec and the contract.
- [ ] Spec has the exact demo curl command(s) and expected response.
- [ ] No sprint touches more than 2 modules.
