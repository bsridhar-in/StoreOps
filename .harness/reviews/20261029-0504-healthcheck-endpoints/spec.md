# Spec: Public liveness and readiness healthcheck endpoints

STATUS: APPROVED 2026-10-29T05:04:42Z

- Feature prompt: "create healthcheck endpoints. Read the attached deployment workflow at /home/codespace/.vscode-remote/data/agentSessionData/f2f56454-f9bd-4e9d-a97e-54da774f5a10/attachments/4153ff0f-4f57-4f2a-b73e-9f6704c659e2/file_deploy.yml and the repository context needed for planning."
- Run slug: `healthcheck-endpoints`
- Modules touched: `core`, `app`

## Summary
The deployed StoreOps API needs unauthenticated liveness and readiness probes on port 8080 so infrastructure clients can distinguish a running process from a fully initialized application. The implementation keeps these infrastructure endpoints separate from StoreOps tenant resources and the existing X-User-ID/X-Store-ID authentication model.

The attached workflow builds and pushes the StoreOps Docker image, renders the ECS task definition, and deploys it to ECS service `storeops-taskdefinition-service` in cluster `ambitious-wolf-thfgx9`, waiting for service stability. It contains no ECS container `healthCheck`, no load-balancer target-group health-check configuration, and no Docker health-check configuration; therefore this feature adds the public API routes but does not wire or enable an infrastructure health check.

## Domain gaps
| # | Prompt concept | Exists in code? | Proposed additive change | Sprint |
|---|---|---|---|---|
| G1 | Liveness healthcheck | No | Add an unauthenticated `GET /health/live` route that reports whether the ASGI process is serving requests. | 1 |
| G2 | Readiness healthcheck | No | Add an unauthenticated `GET /health/ready` route that reports whether application composition completed and required services are available in `app.state`. | 1 |
| G3 | Deployment health-check wiring | No in attached workflow | Keep no ECS, load-balancer target-group, or Docker health-check configuration in this feature; the workflow deploys StoreOps to ECS but does not reference the new routes. | 1 |

## Boundary changes requiring approval

None. The endpoints are added in the composition root/core infrastructure; no module dependency edge, import-linter contract, authentication contract, event, or protected architecture file changes are required.

## API surface
| Method + path | Request | Success | Errors (status code / error.code) |
|---|---|---|---|
| `GET /health/live` | No headers or body | `200 {"status":"alive"}` | No business errors; unexpected application failure prevents the route from responding |
| `GET /health/ready` | No headers or body | `200 {"status":"ready"}` | No business errors; if composition initialization is incomplete, return `503 {"status":"not_ready"}` without an AppError |

## Events
| Event (core/events.py) | Emitted by | Handled by | Payload |
|---|---|---|---|
| None | None | None | No cross-module state change |

## Sprints
| Sprint | Goal | Modules | ACs | Contract |
|---|---|---|---|---|
| 1 | Add public liveness and readiness probes | `core`, `app` | AC-1.1 - AC-1.4 | `sprint-1-contract.md` |

## Open questions for the developer
1. The attached workflow contains no ECS container `healthCheck`, no load-balancer target-group health-check configuration, and no Docker health-check configuration. The default assumption is that neither liveness nor readiness routes are wired automatically by this workflow; wiring them remains a later deployment change and the workflow will not be edited in this feature.
2. Readiness is defined as successful application composition and the presence of all required services on `app.state`. The default assumption is that external database checks are out of scope because this repository currently uses in-memory repositories and has no database health dependency.

## Demo (run after the harness completes)
```bash
.venv/Scripts/uvicorn storeops.main:app --host 0.0.0.0 --port 8080
curl -s http://127.0.0.1:8080/health/live
curl -s http://127.0.0.1:8080/health/ready
```
Expected response: liveness returns HTTP 200 with `{"status":"alive"}`; readiness returns HTTP 200 with `{"status":"ready"}`.
