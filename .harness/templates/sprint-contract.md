# Sprint <N> contract: <goal>

- Spec: `.harness/output/spec.md`
- Modules: <max 2 + core/app.py>
- Depends on: <sprint N-1 | none>

## Scope
<what this sprint delivers, in 2-4 bullets>

## Files expected to change
| File | Layer | Change |
|---|---|---|

## Acceptance criteria

### AC-<N>.1 <short name>
GIVEN <state, with identities from tests/headers.py>
WHEN <actor> <request or service call>
THEN <observable business state: body fields, persisted state via follow-up read, error.code>
AND <side effect: event, alert, metric>

### AC-<N>.2 <store isolation>
...

## Events
- EMIT <EventName> from <module>
- HANDLE <EventName> in <module>
<or "- None">

## Approved protected-file changes
- <path>   (<exact edit, spec item Bn>)
<or "- None">

## Out of scope
<explicitly excluded behaviour, to stop scope creep (L9)>
