# Evaluator feedback - sprint 1, iteration 1

<!-- VERDICT:BEGIN -->
VERDICT: PASS
SCORE: 100.0 / 100
HARD GATES FAILED: none

| Dimension | Weight | Score |
|---|---|---|
| D1 Architecture compliance | 40% | 100.0 |
| D2 Functional correctness and test quality | 35% | 100.0 |
| D3 Code quality and conventions | 25% | 100.0 |

| Check | Severity | Result | Reason |
|---|---|---|---|
| A5 | hard | PASS | import-linter: Contracts: 11 kept, 0 broken. |
| A6 | hard | PASS | error contract: 0 raw raise(s) in service/routes |
| A11 | hard | PASS | event wiring: 1 EMIT, 0 HANDLE, 0 missing |
| A12 | hard | PASS | protected files: 0 unapproved; approved = none |
| L1 | hard | PASS | clone_template_into_programme writes all Activity records to the repository first, then publishes exactly one ActivitiesTemplateCloned event; no other module's service or Reader is used to write. |
| L2 | major | PASS | No routes.py or repository.py changed this sprint (service-level only, per contract). The new service method contains only validation, load-through-Reader, construction, repository writes, and one event publish - no HTTP/route or storage-layer code mixed in. |
| L3 | hard | PASS | modules/reports is not touched by this diff. |
| L4 | major | PASS | NotFoundError(code="PROGRAMME_NOT_FOUND") used for both unknown programme id and cross-store programme id (existence never revealed, matches R3 table and app-context store-isolation rule); ValidationError(code="UNKNOWN_TEMPLATE_KEY") used for the unknown template_key, a body-semantics error. Both codes are SCREAMING_SNAKE and domain-prefixed. |
| L5 | minor | PASS | No new service/subscriber constructed anywhere outside app.py (the method is added to the existing ActivityService class, which app.py already wires). The cross-module read uses the already-exported ProgrammeReader.exists_in_store Protocol method, not a repository import. No protected-file edits were made. |
| A4 | hard | PASS | pytest: 59 passed in 5.42s |
| A7 | hard | PASS | coverage: service 99.0% (min 80), routes 94.4% (min 70), shared 98.6% (min 60), overall 98.5% (min 70) |
| A8 | hard | PASS | changed-file coverage: 4 file(s) checked |
| A9 | hard | PASS | assertion quality: 1 changed test file(s), 0 status-only test(s) |
| A10 | hard | PASS | AC traceability: 4/4 ACs referenced |
| L6 | hard | PASS | Each AC's THEN clause is asserted on business state, not just a status code (there is no HTTP layer this sprint): AC-1.1 asserts exact field values on all 4 created Activity objects in catalog order, a follow-up get_activity() read, and the single published event's fields; AC-1.2/1.3 assert the raised error code plus list_activities() is empty and no event received; AC-1.4 asserts the error code plus no activity/no event. Deleting the new service branch would make every one of these assertions fail. |
| L7 | major | PASS | This sprint adds no endpoint (route is sprint 2, explicitly out of scope), so the auth-header negative path does not apply yet. The negative paths that do apply at the service layer - unknown resource (AC-1.2), other-store isolation (AC-1.3), and invalid body/key (AC-1.4) - are each tested with an exact error code and a verified empty side-effect (no activity created, no event published). No partial-failure or permission rule applies to this method. |
| L8 | major | PASS | Every AC row marked PASS in generator-summary.md cites a test that exists and does prove the AC (verified above), and the files table lists all five changed files with the correct layer (model, model/data, service, shared, test) matching the actual diff. |
| L9 | major | PASS | All four ACs are implemented and nothing beyond contract scope was added: no route, no reports/alerts subscriber, no extra template keys, exactly matching 'Out of scope'. |
| A1 | hard | PASS | ruff check: clean |
| A2 | hard | PASS | ruff format: clean |
| A3 | hard | PASS | mypy --strict: clean |
| L10 | major | PASS | No new schemas this sprint (none required). StrEnum member PLANOGRAM uses an UPPER name with lowercase value "planogram". Error codes are SCREAMING_SNAKE and domain-prefixed. The only query (exists_in_store) is scoped by store_id. PlanogramTaskDefinition is a plain frozen dataclass per models.py conventions, not a schema, so Create/Update/Out naming does not apply. |
| L11 | minor | PASS | No new repository introduced this sprint; the existing InMemoryActivityRepository is reused via the Protocol it already implements. |
| L12 | minor | PASS | No print(), no commented-out code, no TODOs, and no unused helpers in the diff; generator-summary.md's Known gaps section correctly notes the only deferred items (route, reports handling) as out-of-scope for this sprint rather than hidden TODOs. |
<!-- VERDICT:END -->

## Blocking findings (hard gates, then major)
None.

## Minor findings
None.

## Previous findings resolved (iteration > 1)
N/A - iteration 1.

## Generator self-check vs evaluation
| AC | Generator said | Evaluator found | Evidence |
|---|---|---|---|
| AC-1.1 | PASS | PASS | `tests/test_activities_service.py::test_clone_creates_the_standard_planogram_task_set` asserts all 4 Activity fields in catalog order, a follow-up `get_activity` read, and the single `ActivitiesTemplateCloned` event's fields. |
| AC-1.2 | PASS | PASS | `test_clone_rejects_unknown_programme_id` asserts `NotFoundError` code `PROGRAMME_NOT_FOUND`, empty repository, no event. |
| AC-1.3 | PASS | PASS | `test_clone_rejects_programme_from_another_store` asserts the same `PROGRAMME_NOT_FOUND` code (no existence leak across stores), both stores' activity lists empty, no event. |
| AC-1.4 | PASS | PASS | `test_clone_rejects_unknown_template_key` asserts `ValidationError` code `UNKNOWN_TEMPLATE_KEY`, empty repository, no event. |

## Observations (not scored)
- All 12 automated gates (A1-A12) and all 12 LLM checks (L1-L12) pass with no findings; this
  is a clean, correctly-scoped, service-only sprint that matches the contract exactly (no
  route, no reports/alerts wiring, matching "Out of scope").
