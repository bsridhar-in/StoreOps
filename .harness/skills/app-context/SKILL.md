# Skill: app-context (shared foundation - every agent reads this first)

**Purpose.** Tell every agent what StoreOps is, how this repository is laid out today, and
which names in the code correspond to the business vocabulary used in feature prompts. The
code is the source of truth: when a prompt and the code disagree, the code wins and the
Planner records the gap in `spec.md` for the developer to approve.

## 1. Product

StoreOps is a REST API for retail store operations used by an eight-developer squad. It
lets store staff run operational activities (restocking, planogram resets, compliance
checks), group them into store programmes (seasonal rollouts, refits), receive in-app
alerts, and lets managers see store/regional performance.

## 2. Stack (pinned in `pyproject.toml`)

| Concern | Choice |
|---|---|
| Language | Python >= 3.12 (local venv is 3.13), `from __future__ import annotations` everywhere |
| Web | FastAPI >= 0.115, Pydantic v2 schemas, uvicorn |
| Storage | In-memory repositories (`InMemory*Repository`) - no database yet |
| Tests | pytest + `httpx.AsyncClient(ASGITransport)`, `anyio` marker, pytest-cov |
| Static checks | `ruff check`, `ruff format`, `mypy --strict` (pydantic plugin), `lint-imports` |
| Run locally | `.venv/Scripts/uvicorn storeops.main:app --reload` -> http://127.0.0.1:8000/docs |

Windows dev machines: use `.venv/Scripts/<tool>`; CI (Linux) uses `python -m <tool>`.

## 3. Repository map

```
src/storeops/
  app.py          composition root: builds repos -> services -> subscriptions -> routers
  main.py         ASGI entrypoint (app = create_app())
  core/           shared infrastructure - NEVER imports storeops.modules
    errors.py     AppError hierarchy (code, message, status_code, details)
    http.py       AppError/RequestValidationError -> {"error": {...}} envelope
    events.py     EventBus (publish/subscribe) + every DomainEvent dataclass
    auth.py       stub AuthContext from X-User-Id / X-Store-Id / X-Role headers
    clock.py      utcnow()   ids.py  new_id(prefix)
  modules/<name>/ __init__.py (public API), routes.py, service.py, repository.py,
                  models.py (dataclasses + StrEnums), schemas.py (Pydantic I/O)
tests/            test_<module>_api.py (HTTP), test_<module>_service.py (unit),
                  test_architecture.py (AST boundary rules - PROTECTED), headers.py
.harness/         this harness (agents, skills, scripts, output, reviews)
```

## 4. Modules and their responsibility

| Module (package) | Business name in prompts | Owns (code) | Public API exported in `__init__.py` |
|---|---|---|---|
| `activities` | activities / tasks | `Activity`, `ActivityStatus`, `ActivityPriority`, `ActivityCategory` | `Activity`, `ActivityStatus`, `ActivityService`, `InMemoryActivityRepository`, `router` |
| `programmes` | programmes / projects | `Programme` (with `member_ids`) | `Programme`, `ProgrammeReader`, `ProgrammeService`, `InMemoryProgrammeRepository`, `router` |
| `staff` | staff / users | `StaffMember` (id, store_id, name, role) | `StaffMember`, `StaffReader`, `StaffService`, `DEMO_STAFF`, `router` |
| `alerts` | alerts / notifications | `Alert`, `AlertType` | `Alert`, `AlertType`, `AlertService`, `InMemoryAlertRepository`, `router` |
| `reports` | reports | `StoreMetrics`, `RegionMetrics` (event-fed counters) | `ReportService`, `InMemoryMetricsRepository`, `StoreMetrics`, `RegionMetrics`, `router` |

Current allowed module dependency graph (`tests/test_architecture.py::ALLOWED_DEPENDENCIES`):
`activities -> programmes, staff`; `programmes -> staff`; `staff`, `alerts`, `reports` -> none.

## 5. Glossary: brief vocabulary -> code (read before planning or coding)

The client brief uses names that the scaffold does not (yet) use. Default mappings:

| Brief term | Code today | Rule |
|---|---|---|
| Task, TaskStatus | `Activity`, `ActivityStatus` | Use the code names. Never introduce a parallel `Task` class. |
| TaskStatus `TODO/IN_PROGRESS/DONE/BLOCKED` | `ActivityStatus.TODO/IN_PROGRESS/DONE/BLOCKED`, values `"todo"`, `"in_progress"`, `"done"`, `"blocked"` | Identical semantics; wire values are lowercase. |
| TaskPriority `CRITICAL` | `ActivityPriority.URGENT` (`"urgent"`) | Treat CRITICAL == URGENT. Renaming the enum is a breaking API change - only with an approved spec item. |
| TaskCategory `RESTOCKING/PLANOGRAM/AUDIT/COMPLIANCE/GENERAL` | `ActivityCategory` = `merchandising, inventory, customer_service, compliance, maintenance, other` | No `PLANOGRAM`/`RESTOCKING`/`AUDIT` value exists. A feature that needs one must add it in a sprint AC (additive enum change). |
| Project, ProjectMember | `Programme`, `Programme.member_ids` | No `ProjectRole` per member exists yet. |
| StaffRole `REGIONAL_MANAGER/STORE_MANAGER/DEPARTMENT_LEAD/ASSOCIATE` | `core.auth.Role` = `staff`, `store_manager` only | "Department Lead", "Regional Manager" do not exist. Adding a role touches `core/auth.py` + `DEMO_STAFF`; must be an explicit AC. |
| Notification, NotificationChannel | `Alert` (in-app only), `AlertType` | Only IN_APP exists. |
| Report, ReportType, ReportStatus | Not present - `reports` only holds `StoreMetrics` counters | A persisted `Report` record is new work (model + repository inside `reports`). |
| Region | Not present - stores carry only `store_id` | A region -> stores mapping must be introduced explicitly (e.g. a reader in `staff` or a config map in `reports`). |
| Due date / overdue | Not present on `Activity` | Adding `due_at` is an additive model + schema change. |
| Audit entry | Not present | Must be designed in the spec (owned by the module whose state changed). |
| `EventBus.emit()` | `EventBus.publish(event)` | Same concept; the method is `publish`. |
| `throw new Error()` | `raise ValueError(...)` / any built-in / `HTTPException` | All forbidden in services and routes; use `AppError` subclasses. |

## 6. Auth and tenancy (applies to every endpoint)

- Identity comes from headers via `ctx: Auth` (`storeops.core.auth`). Missing headers -> 401
  `UNAUTHORIZED`; unknown role -> 401 `UNKNOWN_ROLE`.
- **Store isolation is a business rule**: every read and write is filtered by
  `ctx.store_id`. A resource in another store is reported as **404 `<THING>_NOT_FOUND`**,
  never 403 (do not leak existence).
- `ctx.is_store_manager` is the only elevated permission today (e.g. delete any activity).
- Demo identities for tests and curl: `tests/headers.py` (`MANAGER`, `ALEX`, `SAM`,
  `OTHER_STORE`), backed by `DEMO_STAFF` in `staff/repository.py`.

## 7. Demonstrating a feature

Every feature must be callable on the running app after the harness run:

```bash
.venv/Scripts/uvicorn storeops.main:app --port 8000
curl -s -X POST http://127.0.0.1:8000/api/activities -H "X-User-Id: staff-001" -H "X-Store-Id: store-001" -H "Content-Type: application/json" -d '{"title":"Restock aisle 4"}'
```

The Planner's spec must contain the exact curl commands for the demo (section "Demo").
