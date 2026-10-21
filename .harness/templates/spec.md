# Spec: <feature title>

STATUS: AWAITING APPROVAL

- Feature prompt: "<verbatim prompt>"
- Run slug: `<kebab-case-slug>`
- Modules touched: <activities, ...>

## Summary
<3-6 sentences: the business outcome for store staff, in StoreOps code vocabulary.>

## Domain gaps
| # | Prompt concept | Exists in code? | Proposed additive change | Sprint |
|---|---|---|---|---|
| G1 | <e.g. CRITICAL priority> | <ActivityPriority.URGENT> | <use URGENT; no change> | - |

## Boundary changes requiring approval
| # | Protected file | Exact edit | Why |
|---|---|---|---|
| B1 | <tests/test_architecture.py> | <ALLOWED_DEPENDENCIES["reports"] = {"activities"}> | <rollup reads activities via ActivityReader> |
<or "None.">

## API surface
| Method + path | Request | Success | Errors (status code / error.code) |
|---|---|---|---|

## Events
| Event (core/events.py) | Emitted by | Handled by | Payload |
|---|---|---|---|

## Sprints
| Sprint | Goal | Modules | ACs | Contract |
|---|---|---|---|---|
| 1 | | | AC-1.1 - AC-1.n | `sprint-1-contract.md` |

## Open questions for the developer
<numbered; each with the Planner's default assumption if unanswered>

## Demo (run after the harness completes)
```bash
.venv/Scripts/uvicorn storeops.main:app --port 8000
curl -s -X <METHOD> http://127.0.0.1:8000/<path> -H "X-User-Id: staff-001" -H "X-Store-Id: store-001" -H "Content-Type: application/json" -d '<body>'
```
Expected response: <status + JSON excerpt>
