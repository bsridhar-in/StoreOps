# Skill: module-patterns (Generator; Evaluator uses it for L1, L2, L5, L11)

**Purpose.** Copyable recipes for the structural pieces of a StoreOps feature: a new
repository, a Reader Protocol for cross-module reads, a domain event with publisher and
subscriber, and composition-root wiring. Each recipe mirrors code already in `src/`.

## 1. Repository = Protocol + InMemory implementation

```python
# src/storeops/modules/activities/repository.py
class ActivityAuditRepository(Protocol):
    def add(self, entry: ActivityAuditEntry) -> None: ...

    def list_for_activity(self, activity_id: str) -> list[ActivityAuditEntry]: ...


class InMemoryActivityAuditRepository:
    def __init__(self) -> None:
        self._items: list[ActivityAuditEntry] = []

    def add(self, entry: ActivityAuditEntry) -> None:
        self._items.append(entry)

    def list_for_activity(self, activity_id: str) -> list[ActivityAuditEntry]:
        return [e for e in self._items if e.activity_id == activity_id]
```

- Services are typed against the Protocol (`repo: ActivityRepository`), `app.py` passes the
  `InMemory*` class. Export the `InMemory*` class from the module `__init__.py`.
- Repositories filter by arguments only; they never read `ctx`, never check permissions,
  never publish events (import-linter `R4-repositories-are-pure-data-access`).
- A new repository belongs to exactly one module. Another module never gets it injected.

## 2. Cross-module read: a Reader Protocol

Pattern already used: `StaffReader` (staff/service.py), `ProgrammeReader` (programmes/service.py).

```python
# src/storeops/modules/activities/service.py
class ActivityReader(Protocol):
    """Read-only activity lookups exposed to other modules."""

    def list_for_stores(self, store_ids: Sequence[str]) -> list[Activity]: ...
```

1. Define the Protocol in the **owning** module's `service.py`; the owning service implements
   it structurally (no inheritance needed).
2. Export it (and the entity type it returns) from the owning `__init__.py` and `__all__`.
3. The consumer imports `from storeops.modules.activities import ActivityReader` and takes it
   as a constructor argument. Reader methods are side-effect free and return domain
   dataclasses or primitives.
4. Adding the edge needs an approved boundary change (`architecture-principles`).

## 3. Cross-module side effect: a DomainEvent

```python
# 1. src/storeops/core/events.py  (core never imports modules -> primitives only)
@dataclass(frozen=True, kw_only=True)
class ActivitiesBulkUpdated(DomainEvent):
    activity_ids: tuple[str, ...]
    status: str                     # ActivityStatus.value, not the enum
    updated_by: str

# 2. publisher - activities/service.py, after the repository writes
self._bus.publish(
    ActivitiesBulkUpdated(
        store_id=ctx.store_id,
        activity_ids=tuple(a.id for a in updated),
        status=status.value,
        updated_by=ctx.user_id,
    )
)

# 3. subscriber - alerts/service.py (or reports/service.py)
def register(self, bus: EventBus) -> None:
    ...
    bus.subscribe(ActivitiesBulkUpdated, self._on_activities_bulk_updated)

def _on_activities_bulk_updated(self, event: ActivitiesBulkUpdated) -> None:
    ...
```

- Publish once per business transaction (one bulk event, not N single events) unless the
  contract says otherwise; publish only for items that actually changed.
- Subscribers live in `alerts`/`reports` (or any module reacting to another), update only their
  own repository, and use `_on_<event_snake>` naming.
- Time-based triggers (e.g. SLA breach after a due date) are not handled by a thread. Expose a
  service method such as `ActivityService.detect_sla_breaches(now: datetime)` that publishes
  `ActivitySlaBreached` events, plus a store-manager-only route
  (`POST /api/activities/sla-scan`) to invoke it; tests pass `now` explicitly.
- Strings that match enum values across modules (e.g. `_DONE_STATUS = "done"` in reports) are
  declared as module constants in the subscriber, as `reports/service.py` does today.

## 4. Composition root (`src/storeops/app.py`)

```python
activity_service = activities.ActivityService(
    activities.InMemoryActivityRepository(),
    staff_service,
    programme_service,
    bus,
    audit_repo=activities.InMemoryActivityAuditRepository(),   # new dependency
)
report_service = reports.ReportService(reports.InMemoryMetricsRepository(), activity_service)
report_service.register(bus)
```

- `app.py` is the only file that constructs services, passes concrete services as Readers,
  calls `register(bus)`, and sets `app.state.<name>_service`.
- A new router is added to the `for router in (...)` tuple; new module packages also need a
  rule in `ALLOWED_DEPENDENCIES` (protected file - spec approval).
- Keep constructor parameters backwards compatible (keyword with default) when existing tests
  build the service directly.

## 5. Checklist per changed file (copy into generator-summary.md "Layer" column)

| File | Layer | Allowed content |
|---|---|---|
| `modules/x/routes.py` | route | HTTP mapping only |
| `modules/x/schemas.py` | route (I/O contract) | Pydantic request/response models |
| `modules/x/service.py` | service | rules, permissions, scoping, events, Reader Protocols |
| `modules/x/repository.py` | repository | Protocol + InMemory storage |
| `modules/x/models.py` | domain | dataclasses, StrEnums |
| `core/events.py` | shared | DomainEvent dataclasses |
| `core/errors.py` | shared | AppError subclasses |
| `app.py` | composition root | wiring only |
| `tests/...` | test | see `how-to-test` |
