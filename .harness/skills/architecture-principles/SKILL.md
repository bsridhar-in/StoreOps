# Skill: architecture-principles (shared foundation - every agent)

**Purpose.** The five non-negotiable StoreOps architecture rules, how each maps to a failure
mode seen in the earlier AI experiment, exactly how the harness detects a violation, and the
procedure for a legitimate change to a boundary. Planner plans within these rules, the
Generator codes within them, the Evaluator enforces them.

| Rule | Failure mode it prevents | Automated gate | LLM-assessed check |
|---|---|---|---|
| R1 Module boundary | FM1 direct import of another module's repository | A5 `lint-imports` contracts `R1-repository-encapsulation*` + `tests/test_architecture.py` | L5 |
| R2 Event bus only | FM4 state changes written straight into sibling modules | A5 contracts `R2-event-bus-only*`, A11 event wiring | L1 |
| R3 Error contract | FM2 raw `Error` throws | A6 AST scan, A1 ruff `TID251` (bans `HTTPException`), `test_services_and_routes_raise_only_app_errors` | L4 |
| R4 Layer separation | business logic in routes, I/O in repositories | A5 contracts `R4-layers`, `R4-no-layer-skipping`, `R4-repositories-are-pure-data-access` | L2 |
| R5 Read-only reports | reports writing to source modules | A5 (no repository imports) | L3 |

FM3 (tests that only check status codes) is covered by `how-to-test` and gates A9/A10/L6.

---

## R1 - Module boundary

**Rule.** No module imports another module's `repository` (or any internal file). Cross-module
*reads* go through the target module's **package** (`from storeops.modules.programmes import
ProgrammeReader`) and only through a read-only `<Name>Reader` Protocol that the target exports.

```python
# CORRECT - activities/service.py today
from storeops.modules.programmes import ProgrammeReader
from storeops.modules.staff import StaffReader

# WRONG - FM1, caught by A5 (R1-repository-encapsulation-programmes)
from storeops.modules.programmes.repository import InMemoryProgrammeRepository
# WRONG - internal import, caught by test_architecture.py (public package only)
from storeops.modules.programmes.service import ProgrammeService
```

- `staff` is read-only to everyone: other modules may import only `StaffReader`, `StaffMember`.
- The dependency graph must stay acyclic and match `ALLOWED_DEPENDENCIES` in
  `tests/test_architecture.py` (`activities -> programmes, staff`; `programmes -> staff`).
- Only `app.py` (composition root) may import every module and pass concrete services into
  constructors typed as Reader Protocols.

## R2 - Event bus only for cross-module side effects

**Rule.** When a state change in module A must cause something in module B (alert a lead,
count a completion, create a report record), A calls `self._bus.publish(SomethingHappened(...))`
and B subscribes in its `register(bus)` method. A never imports B's service, and never calls
a Reader to *write*. `alerts` and `reports` are imported by nobody except `app.py`.

```python
# CORRECT - publish, in the service, after the repository write succeeded
self._repo.update(updated)
self._bus.publish(ActivityUpdated(store_id=ctx.store_id, activity_id=updated.id, ...))

# WRONG - FM4: direct service-to-service side effect (A5 R2-event-bus-only BROKEN)
from storeops.modules.alerts import AlertService
self._alerts.raise_sla_breach(...)
```

- Event dataclasses live **only** in `src/storeops/core/events.py`, are
  `@dataclass(frozen=True, kw_only=True)`, subclass `DomainEvent` (carries `store_id`,
  `occurred_at`), and carry primitive/str fields (enum `.value`, not module enums - `core`
  cannot import modules).
- Name events in past tense: `ActivitiesBulkUpdated`, `ActivitySlaBreached`, `ProgrammeClosed`.
- Every sprint contract lists its events as `- EMIT <Event> from <module>` /
  `- HANDLE <Event> in <module>`; A11 verifies each is defined, published and subscribed.
- Publish inline (`self._bus.publish(Event(...))`) so A11 can find it.
- `EventBus` dispatches by exact type and isolates failing handlers; a handler must not raise
  to signal business failure.

## R3 - Error contract

**Rule.** Services and routes raise only `AppError` subclasses from `storeops.core.errors`
with a domain-specific `code`. Never `raise ValueError/KeyError/RuntimeError/Exception`, never
`fastapi.HTTPException`, never `return JSONResponse(status_code=4xx)` for errors.

| Situation | Class | Status | Example code |
|---|---|---|---|
| Body semantically invalid / reference to unknown thing | `ValidationError` | 422 | `UNKNOWN_ASSIGNEE`, `INVALID_FIELD` |
| Missing / bad auth headers | `UnauthorizedError` | 401 | `UNAUTHORIZED` |
| Authenticated but not allowed | `ForbiddenError` | 403 | `ACTIVITY_DELETE_FORBIDDEN` |
| Not found **or in another store** | `NotFoundError` | 404 | `ACTIVITY_NOT_FOUND` |
| Conflicts with current state | `ConflictError` | 409 | `ALREADY_A_MEMBER` |
| Unexpected | `InternalError` | 500 | `INTERNAL_ERROR` |

Pydantic validators in `schemas.py` may `raise ValueError` - FastAPI converts it into the 422
`VALIDATION_ERROR` envelope. That is the only place a built-in raise is allowed.

## R4 - Layer separation (Routes -> Service -> Repository, no skipping)

| Layer | May | Must not |
|---|---|---|
| `routes.py` | declare path/method/status, take `ctx: Auth`, Pydantic body/query, call **one** service method, map to `*Out` | import a repository, loop over business rules, check permissions, publish events, touch `app.state` except in the `get_<x>_service` dependency |
| `service.py` | enforce business rules, permissions, store scoping, call repository + Readers, publish events, raise `AppError` | import fastapi/Request/Response, return Pydantic `*Out` objects |
| `repository.py` | `Protocol` + `InMemory*` implementation; store/query dataclasses, filter by arguments | import fastapi/httpx/`core.events`/`core.http`, call services, raise HTTP errors, apply permissions |

The `generator-summary.md` must state the layer of every changed file.

## R5 - Read-only reports

`reports` aggregates activities/programmes/staff data. It may (a) subscribe to events and
update its **own** repository, (b) call another module's Reader Protocol for read-only lookups
(requires an approved dependency change, below), and (c) publish its own events. It must never
call a method that mutates another module, never import another module's repository, and
never publish an event whose purpose is to make another module change its own state on
reports' behalf.

---

## Changing a boundary (the only legal way)

Some features legitimately need a new edge, e.g. a regional rollup where
`reports -> activities` reads through an `ActivityReader`. Procedure:

1. **Planner** lists it in `spec.md` under "Boundary changes requiring approval" with the
   exact edits: `ALLOWED_DEPENDENCIES` in `tests/test_architecture.py`, and
   `R2-event-bus-only`/import-linter contract lines in `pyproject.toml` if affected.
2. Developer types `APPROVED` (approval covers exactly the listed edits).
3. The sprint contract lists the files under `## Approved protected-file changes`.
4. Generator makes only those edits; A12 fails any other protected-file change.
5. Evaluator checks the edit matches the spec text exactly (L5).

Protected paths (from `.harness/config.json`): `CLAUDE.md`, `pyproject.toml`,
`tests/test_architecture.py`, `tests/conftest.py`, `.harness/agents|skills|scripts|templates/**`,
`.harness/config.json`, `.claude/**`, `.github/**`. Weakening a check to make code pass is
always a FAIL - never "approve" that.
