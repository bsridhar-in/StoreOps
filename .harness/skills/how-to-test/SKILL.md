# Skill: how-to-test (Generator writes tests with it; Evaluator grades A4, A7-A10, L6, L7)

**Purpose.** What a StoreOps test must prove. The earlier experiment produced tests that
asserted `status_code == 200` and nothing else (failure mode 3). In this repo a test exists to
prove a **business rule** from the sprint contract; the status code is only the first assertion.

## 1. Thresholds (enforced by `run_checks.py`, config in `.harness/config.json`)

| Scope | Files | Min line coverage | Check |
|---|---|---|---|
| Service layer | `src/storeops/modules/*/service.py` | 80% | A7 aggregate, A8 per changed file |
| Route layer | `src/storeops/modules/*/routes.py` | 70% | A7, A8 |
| Shared utilities | `src/storeops/core/*.py` | 60% | A7, A8 |
| Overall | `src/storeops/**` | 70% | A7; other changed files A8 |

Baseline today is ~98% overall: a sprint that lowers a scope materially is suspicious even if
above the line. Run: `.venv/Scripts/python -m pytest --cov --cov-report=term-missing`.

## 2. Traceability (A10)

Every `AC-N.M` in the sprint contract appears in at least one test **docstring**:

```python
async def test_bulk_update_marks_done_and_records_audit(client: httpx.AsyncClient) -> None:
    """AC-1.1, AC-1.4: outgoing shift marks activities DONE; one audit entry per activity."""
```

## 3. What counts as a business assertion (A9, L6)

A9 fails any **changed** test function whose only assertions mention `status_code`. L6 then
checks that each AC's THEN clause is asserted. Assert at least one of:

- Response body fields that encode the rule (`body["results"][2] == {"id": c, "status": "failed", "code": "ACTIVITY_NOT_FOUND", ...}`).
- Persisted state through a follow-up read (`GET /api/activities/{id}` -> `"done"`), and that
  untouched records are **unchanged**.
- The error envelope **code** (`response.json()["error"]["code"] == "INVALID_BULK_STATUS"`), not
  just 422.
- Side effects through the bus: alerts via `GET /api/alerts` as the recipient, metrics via
  `app.state.report_service.get_store_metrics("store-001")`, or a captured event:

```python
def test_bulk_update_publishes_one_event(app: FastAPI) -> None:
    """AC-1.5"""
    received: list[ActivitiesBulkUpdated] = []
    app.state.event_bus.subscribe(ActivitiesBulkUpdated, received.append)
    ...
    assert [e.activity_ids for e in received] == [(a_id, b_id)]
```

Helpers named `assert_*` / `expect_*` count as business assertions for A9 - use them for
repeated checks (e.g. `assert_error(response, 404, "ACTIVITY_NOT_FOUND")`). A9 treats any
`assert` whose text mentions `status_code` as a status assertion, so keep the status check
and the business check in **separate** `assert` statements; `pytest.raises(SomeAppError)`
also counts as a business assertion in service tests.

## 4. Required negative paths (L7)

For every new or changed endpoint:

| Case | Expectation |
|---|---|
| No auth headers | 401, `error.code == "UNAUTHORIZED"` |
| Resource in another store (`OTHER_STORE` headers or id) | 404 `<THING>_NOT_FOUND`, and the other store's data unchanged |
| Invalid body / enum / extra field | 422 with exact `code` (`VALIDATION_ERROR` from Pydantic, or the domain code) |
| Permission rule (if any) | 403 with exact domain code, state unchanged |
| Partial failure (bulk endpoints) | mixed result list, successes persisted, failures untouched |
| Event subscriber | effect visible, and **not** triggered for self-actions if the rule says so (see `AlertService._on_activity_updated`) |

## 5. Structure and fixtures

- HTTP tests: `tests/test_<module>_api.py`, `pytestmark = pytest.mark.anyio`, fixture
  `client: httpx.AsyncClient` from `tests/conftest.py` (fresh `create_app()` per test - no
  shared state). Identities from `tests/headers.py` (`ALEX`, `SAM`, `MANAGER`, `OTHER_STORE`).
- Service/unit tests: `tests/test_<module>_service.py`, construct the service with
  `InMemory*` repositories and a real `EventBus` (see `tests/test_reports_service.py`). No mocks
  of our own classes; a tiny fake Reader implementing the Protocol is fine.
- Time: pass `now` explicitly to time-based service methods; never `sleep`.
- Arrange / Act / Assert separated by blank lines; one behaviour per test; name
  `test_<behaviour>` in plain words.
- Never edit `tests/test_architecture.py` or `tests/conftest.py` without an approved contract
  entry (A12). Never delete or weaken an existing test to make a sprint pass.
- New fixtures go in the test file that uses them, or a new `tests/<name>_helpers.py`.

## 6. Anti-patterns the Evaluator fails

- `assert response.status_code == 200` as the only assertion (A9).
- Asserting on `len(body) > 0` instead of exact ids/values.
- Testing the happy path only for a rule that has a failure branch.
- Re-implementing the business rule in the test to compute the expected value.
- Tests that pass with the feature code removed (Evaluator mentally deletes the new service
  branch: would the test still pass? If yes -> L6 FAIL).
