# Sprint 1 contract: Public liveness and readiness probes

- Spec: `.harness/output/spec.md`
- Modules: `core`, composition root
- Depends on: none

## Scope
- Add two unauthenticated health routes to the application composition root.
- Return explicit JSON status payloads without requiring StoreOps identity headers.
- Verify HTTP behavior and readiness failure behavior with ASGI tests.
- Keep the deployment unchanged: the attached workflow deploys StoreOps to ECS but has no ECS container healthCheck, load-balancer target-group health-check, or Docker health-check configuration.

## Files expected to change
| File | Layer | Change |
|---|---|---|
| `src/storeops/app.py` | Composition root | Define `GET /health/live` and `GET /health/ready`, check initialized service state, and register routes on the FastAPI app |
| `tests/test_health_api.py` | HTTP tests | Add ASGI tests for live, ready, no-auth, missing-ready-state, and route documentation behavior |

## Acceptance criteria

### AC-1.1 Liveness responds without identity headers
GIVEN a normally created StoreOps application and no X-User-ID, X-Store-ID, or X-Role headers
WHEN an HTTP client sends `GET /health/live`
THEN the response status is 200 and the JSON body is exactly `{"status":"alive"}`
AND the readiness endpoint may be called independently afterward with no authentication state created

### AC-1.2 Readiness responds when application services are initialized
GIVEN a normally created StoreOps application whose `app.state` contains `staff_service`, `programme_service`, `activity_service`, `alert_service`, and `report_service`
WHEN an HTTP client sends `GET /health/ready`
THEN the response status is 200 and the JSON body is exactly `{"status":"ready"}`
AND the response includes no StoreOps tenant resource data

### AC-1.3 Readiness reports an incomplete application composition
GIVEN a StoreOps app test instance with one required service intentionally removed from `app.state`
WHEN an HTTP client sends `GET /health/ready`
THEN the response status is 503 and the JSON body is exactly `{"status":"not_ready"}`
AND the same app's liveness endpoint still returns 200 with `{"status":"alive"}`

### AC-1.4 Health routes remain public
GIVEN a normally created StoreOps application and missing identity headers
WHEN an HTTP client sends both `GET /health/live` and `GET /health/ready`
THEN each response has its readiness/liveness status payload rather than HTTP 401 or an error envelope with code `UNAUTHORIZED`

## Events
- None

## Approved protected-file changes
- None

## Out of scope
- Kubernetes probe manifests, ECS task-definition `healthCheck` wiring, load-balancer target-group health-check configuration, Dockerfile or image Docker health-check configuration, and edits to `.github/workflows/*`.
- Database, network, Redis, AWS, or external-service connectivity checks.
- Tenant-specific or authenticated health information.
- Adding health metrics, health events, or health alert subscriptions.
