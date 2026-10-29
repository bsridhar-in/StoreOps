# StoreOps API (Python)

 Testing
REST API for retail store operations management, built with FastAPI. This is a **stub
implementation**: the structure, contracts, and boundary rules are in place, storage is
in-memory, and business logic is minimal.

## Quick start

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -e ".[dev]"

uvicorn storeops.main:app --reload   # http://127.0.0.1:8080/docs
```

Quality gates:

```bash
pytest          # tests (pytest + httpx ASGITransport)
ruff check .    # lint
ruff format --check .
mypy            # strict type checking
lint-imports    # module-boundary contracts (pyproject [tool.importlinter])
python .harness/scripts/run_checks.py --ci   # all of the above + coverage thresholds (CI gate)
```

## AI development harness

AI-assisted changes run through a Planner -> Generator <-> Evaluator -> Monitor harness
orchestrated by [`CLAUDE.md`](CLAUDE.md). In Claude Code: `@planner <feature>`, review
`.harness/output/spec.md`, type `APPROVED`. Agents: `.harness/agents/`, skills:
`.harness/skills/`, rubric: `.harness/skills/grading-criteria/rubric.json`, audit trail:
`.harness/reviews/`.

## Authentication (stub)

The caller's identity is read from headers (placeholder for a real identity provider):

| Header       | Required | Notes                                    |
|--------------|----------|------------------------------------------|
| `X-User-Id`  | yes      | staff id, e.g. `staff-001`               |
| `X-Store-Id` | yes      | e.g. `store-001`                         |
| `X-Role`     | no       | `staff` (default) or `store_manager`     |

Demo staff are seeded in `src/storeops/modules/staff/repository.py` (`DEMO_STAFF`).

## Endpoints

| Method + Path                    | Module     | Description                                             |
|----------------------------------|------------|---------------------------------------------------------|
| `GET /api/activities`            | activities | List activities (`?programme_id=` and `?status=` filters) |
| `POST /api/activities`           | activities | Create a new activity                                   |
| `GET /api/activities/{id}`       | activities | Get activity by ID                                      |
| `PATCH /api/activities/{id}`     | activities | Update status, priority, category, assignee             |
| `DELETE /api/activities/{id}`    | activities | Delete (owner or store manager only)                    |
| `GET /api/programmes`            | programmes | List programmes for the authenticated store             |
| `POST /api/programmes`           | programmes | Create a new programme                                  |
| `POST /api/programmes/{id}/members` | programmes | Add a staff member to a programme                    |
| `GET /api/alerts`                | alerts     | Alerts for the authenticated user (`?unread_only=true`) |

## Architecture

```
src/storeops/
  app.py            composition root - the only place that wires every module
  main.py           ASGI entrypoint
  core/             shared infrastructure (never imports modules)
    errors.py       AppError hierarchy (code, message, status_code)
    http.py         AppError -> JSON error envelope
    events.py       EventBus + domain events
    auth.py         stub auth context
  modules/<name>/   routes.py -> service.py -> repository.py (+ models.py, schemas.py)
    activities  programmes  staff  alerts  reports
```

### Module boundary rules

Enforced by `tests/test_architecture.py`:

- **No circular imports.** Allowed dependencies: `activities -> programmes, staff`,
  `programmes -> staff`; `staff`, `alerts`, and `reports` depend on no module.
- **Public API only.** Cross-module imports go through `storeops.modules.<name>`, never
  internals.
- **Staff (users) is read-only** for other modules: only `StaffReader` / `StaffMember`.
- **Notifications go through the event bus only.** `alerts` and `reports` subscribe to
  events defined in `core/events.py` and never import publishers.
- **Typed errors only.** Services and routes raise `AppError` subclasses, never built-ins.

### Errors

Every error response has the same shape:

```json
{ "error": { "code": "ACTIVITY_NOT_FOUND", "message": "Activity 'act_x' not found", "statusCode": 404 } }
```

| Class               | Status |
|---------------------|--------|
| `ValidationError`   | 422    |
| `UnauthorizedError` | 401    |
| `ForbiddenError`    | 403    |
| `NotFoundError`     | 404    |
| `ConflictError`     | 409    |
| `InternalError`     | 500    |
