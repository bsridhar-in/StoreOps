# Skill: coding-conventions (Generator; Evaluator uses it for L4, L10, L12)

**Purpose.** The concrete Python conventions of this codebase, so generated code is
indistinguishable from the existing modules and passes `ruff`, `ruff format`, and
`mypy --strict` on the first run.

## 1. Automated checks you must run before writing generator-summary.md

```bash
.venv/Scripts/ruff format .
.venv/Scripts/ruff check . --fix
.venv/Scripts/mypy
.venv/Scripts/lint-imports
.venv/Scripts/python .harness/scripts/run_checks.py --sprint <N>
```

`run_checks.py` is the same gate the Evaluator uses. Do not hand over with a FAIL you have
not listed under "Known gaps".

## 2. Files and imports

- Every module file starts with `from __future__ import annotations` when it has type-only
  references (services, repositories); follow the neighbouring file.
- Import order is enforced by ruff `I`. First-party is `storeops`, tests import `tests.headers`.
- Absolute imports only (`from storeops.modules.activities.models import Activity`). Inside a
  module use its internal files; across modules use only the package (`storeops.modules.x`).
- Line length 100. Type hints on every function, including tests (`-> None`) - ruff `ANN`.
- `mypy --strict`: no `Any` leaks, no untyped defs, no `# type: ignore` without a code and
  reason. When reading `request.app.state.x`, annotate the local
  (`service: ActivityService = request.app.state.activity_service`) as existing routes do.

## 3. Models (`models.py`)

- Domain entities are `@dataclass` (mutable records) or `@dataclass(frozen=True)` (values,
  e.g. `StaffMember`). No Pydantic in models.
- Enums are `StrEnum` with **UPPER member names and lowercase values**:
  `DONE = "done"`. Adding a member is additive and allowed when an AC requires it; renaming
  or removing one is a breaking change needing spec approval.
- Timestamps are timezone-aware, from `storeops.core.clock.utcnow()` - never
  `datetime.now()`/`utcnow()` directly (tests may monkeypatch the clock).
- Ids come from `storeops.core.ids.new_id("<prefix>")`. Existing prefixes: `act`, `prg`,
  `alr`. Choose a new 3-letter prefix for new entities (e.g. `aud` audit, `rpt` report).
- Update with `dataclasses.replace(entity, **changes, updated_at=utcnow())`.

## 4. Schemas (`schemas.py`)

- Request models: `<Entity>Create`, `<Entity>Update`, `<Action>Request`
  (e.g. `BulkStatusRequest`) with `model_config = ConfigDict(extra="forbid")`.
- Response models: `<Entity>Out` / `<Action>Result` with
  `model_config = ConfigDict(from_attributes=True)` and built via `Out.model_validate(entity)`.
- Use `Field(min_length=..., max_length=...)`, `Field(max_length=100)` on lists, enums as field
  types (FastAPI turns bad values into 422 `VALIDATION_ERROR`).
- Partial updates use `data.model_dump(exclude_unset=True)`; non-nullable fields explicitly set
  to `null` raise `ValidationError(code="INVALID_FIELD")` in the service (see
  `ActivityService.update_activity`).
- Cross-field rules may use `@model_validator(mode="after")` raising `ValueError` (the one
  sanctioned built-in raise, see `ProgrammeCreate._check_date_range`).

## 5. Errors (rule R3)

```python
from storeops.core.errors import ConflictError, NotFoundError, ValidationError

raise NotFoundError(f"Activity '{activity_id}' not found", code="ACTIVITY_NOT_FOUND")
raise ValidationError("At most 100 ids per request", code="BULK_LIMIT_EXCEEDED",
                      details={"max": 100, "received": len(ids)})
```

- `code` is SCREAMING_SNAKE and domain-prefixed (`ACTIVITY_`, `PROGRAMME_`, `REPORT_`,
  `UNKNOWN_<THING>`); the message names the offending id in single quotes.
- Never `raise ValueError(...)`, `raise Exception`, `raise HTTPException` (ruff TID251 bans
  the import) or `assert` for validation in services/routes.
- Reuse an existing code when the meaning is identical (`ACTIVITY_NOT_FOUND`), never invent a
  synonym (`TASK_MISSING`).
- Need a status not in the hierarchy (e.g. 429)? Add a subclass to `core/errors.py` with
  `default_code` and `status_code` ClassVars plus a parametrised case in `tests/test_core.py`.
- Partial-failure endpoints do not raise for per-item failures: the service catches the
  `AppError` per item and records `{"id", "status": "failed", "code", "message"}` from
  `error.code` / `error.message`.

## 6. Services (`service.py`)

- Constructor takes the repository **Protocol**, Reader Protocols of other modules, and
  `EventBus`, stored as `self._repo`, `self._staff`, `self._programmes`, `self._bus`.
- Every public method takes `ctx: AuthContext` first (except event handlers and Reader
  methods, which take explicit `store_id`).
- Fetch-in-store helper pattern: `get_activity(ctx, id)` raises `NotFoundError` when missing
  *or* `store_id != ctx.store_id`. Reuse it; never re-implement scoping inline.
- Order inside a mutating method: validate -> load (scoped) -> check permission -> build new
  state -> `repo` write -> `bus.publish(...)` -> return the entity.
- Private helpers are `_snake_case`; module constants `_UPPER_CASE` (e.g. `_NON_NULLABLE_FIELDS`).

## 7. Routes (`routes.py`)

```python
router = APIRouter(prefix="/api/activities", tags=["activities"])

def get_activity_service(request: Request) -> ActivityService:
    service: ActivityService = request.app.state.activity_service
    return service

Service = Annotated[ActivityService, Depends(get_activity_service)]

@router.patch("/bulk-status")            # literal paths BEFORE "/{activity_id}"
async def bulk_update_status(body: BulkStatusRequest, ctx: Auth, service: Service) -> BulkStatusResult:
    return BulkStatusResult.model_validate(service.bulk_update_status(ctx, body))
```

- `async def`, explicit return type (the response model), `status_code=` on the decorator for
  201/204. When the status depends on the outcome (200 vs 207), take `response: Response` and
  set `response.status_code` from a field the service returned - no business decision in the route.
- One service call per handler. No loops over items, no permission checks, no `try/except`.

## 8. Hygiene (L12)

No `print`, no commented-out code, no `TODO` unless it is listed in generator-summary
"Known gaps", no unused helpers, no new third-party dependency (pyproject is protected).
Docstrings: one-line module/class docstrings in the style of the existing files; comments
explain *why*, not what.
