# Architecture Journal

A running log of the decisions, trade-offs, and insights that came up while building the
StoreOps harness and running it against the real codebase — in the order they actually
happened, not retrospectively cleaned up. (For the polished design rationale, see
`design_brief.md`; for a scored self-assessment, see `REFLECTION.md`.)

---

## Day 1 — Building the harness itself

### Decision: route the verdict through a script, not through the Evaluator's own words

The brief asked for an evaluation framework that "converts variable output into a binary
per-check result." The first instinct was to let the Evaluator conclude with a verdict line
directly in its feedback. Rejected almost immediately: if the Evaluator *states* PASS/FAIL,
every re-run is a fresh roll of the dice on phrasing and leniency, which defeats the entire
point. **Decision**: the Evaluator only produces evidence (`evaluator-checks.json`, one entry
per L-check, each with file:line); a separate script, `verdict.py`, reads that evidence plus
the automated `checks.json` against a machine-readable `rubric.json` and computes the verdict.
The Evaluator agent file explicitly forbids it from writing a verdict word anywhere else.
**Trade-off**: this adds a layer of indirection — the Evaluator can no longer just "decide" —
and makes the rubric itself a protected, version-controlled artifact that has to be gotten
right once rather than re-litigated per run. Accepted that trade-off because the alternative
(reproducibility) was the whole point of the exercise.

### Insight: hard gates need to be literally un-arguable, not just "important"

Early draft of the rubric had import-linter and the raw-raise scan as *major* severity, not
*hard*. Reconsidered after re-reading the client's four failure modes: a "major" finding still
allows a PASS if the score is high enough elsewhere, which means a sufficiently good-looking
feature could ship with a live module-boundary violation. That's precisely the failure the
standards team is trying to eliminate, so it can't be negotiable on points. Moved A5, A6, A9,
A10, A11, A12 and the test-suite gate (A4) to `hard` severity — any one of them failing forces
FAIL regardless of total score. **Trade-off**: a feature that's 95% excellent can still FAIL
outright for one real boundary violation. That's intentional, not a bug in the design.

### Decision: coverage thresholds differentiated by layer, not a single project-wide number

The brief specified per-layer thresholds (service 80%, routes 70%, shared 60%, overall 70%).
Could have simplified to one overall number for the harness's own bookkeeping. Kept the
per-layer split (`A7` aggregate, `A8` per changed file) because a single blended number hides
exactly the case that matters most here: a well-tested route sitting on top of an
under-tested service layer, which is where business-rule bugs actually live.

### Insight: a banned-API lint rule is cheaper than an AST scan for the same rule, where it applies

`TID251` (ruff's banned-API rule) can ban `fastapi.HTTPException` directly at import time —
faster feedback than waiting for the custom AST scan (`A6`) to run. Kept both: `TID251` catches
the specific `HTTPException` case instantly during `ruff check`; the AST scan is still needed
for the general "no raw built-in `raise`" rule, which `ruff` has no rule for. Neither subsumes
the other; they cover adjacent, not identical, ground.

### Decision: probe the gates with deliberately broken code before trusting them

Before writing a single real feature, planted a module that directly imported another
module's repository, raised `ValueError` and `HTTPException`, asserted only on `status_code`,
and referenced an event that was never defined. All five gates caught their target with
file:line evidence on the first run. **Insight**: this was worth doing *before* any real
feature, not after — it's much cheaper to debug a harness script against code you wrote to
break it than against a real Generator's output where you can't be certain whether a missed
finding is a harness bug or a genuinely subtle violation.

---

## Day 2 — First two real runs; the approval loop in practice

### Insight: the Planner's domain-gap defaults get revisited in practice, not in theory

The regional-rollup-report spec's first draft defaulted to a hardcoded `region_id → stores`
map and restricted the endpoint to a manager viewing only their own region. Both were called
out as open questions with explicit defaults, exactly as `sprint-decomposition/SKILL.md`
requires — and the developer overturned both on review. The re-plan moved `region_id` onto
`StaffMember` (new dependency: `reports → staff`) and dropped the store-membership check
entirely. **Trade-off surfaced only at this point, not before**: moving region membership into
`staff` meant the feature now needed a protected-file edit
(`ALLOWED_DEPENDENCIES["reports"] = {"activities", "staff"}`) that the *first* draft didn't
need at all. The Planner's own sizing rules absorbed this fine — the boundary change simply
moved into the first sprint that needed it — but it's a reminder that "which modules this
touches" isn't always knowable from the prompt alone; it can change after the developer's first
look at the default assumptions.

### Decision: CHANGES re-invokes the Planner fresh, it doesn't patch the existing spec

When the developer said `CHANGES: make the changes accordingly for 1 and 3`, the Planner was
re-invoked as an entirely new subagent with the feedback stated explicitly in its prompt,
rather than trying to have it edit its own prior `spec.md` in place. **Rationale**: a
resolution this structural (moving where region data lives changes which module depends on
which) is easier to get right by re-deriving the whole plan from the feature prompt plus the
explicit feedback than by patching individual lines of an existing spec and hoping the
knock-on consequences (sprint 1's scope, the boundary-change list) got updated consistently.
**Cost**: a full re-plan, not an incremental edit — acceptable since Planner runs are cheap
relative to the Generator/Evaluator loop that follows.

### Insight: store-scoped access is the default worth defending, not a detail

When the developer asked to confirm what "any manager may view any region" actually meant, the
answer that mattered wasn't the mechanics — it's that **every other endpoint in this codebase
gates on `ctx.store_id`**, so removing that gate here is a genuine, visible departure from how
the rest of StoreOps behaves, not a minor permissions tweak. Worth writing that down: when a
feature's access rule breaks the codebase's own pattern, that's exactly the kind of thing a
Planner's "open question with a stated default" is for — it forces the developer to notice the
departure instead of inheriting it silently.

---

## Day 3 — The retention gap, the mistake, the fix, and the merge reckoning

### Insight: "the harness never overwrites what you need" was a claim, not yet a guarantee

Up to this point, `spec.md`, `sprint-N-contract.md`, and every iteration's
`generator-summary.md`/`evaluator-feedback.md` lived only in `.harness/output/`, which is
git-ignored scratch, cleared at the start of every new run. The run-logs were committed; the
artifacts that justify *why* a run passed were not. This had been true since the harness's
first design and nobody had hit it — until the developer asked, directly, whether re-running
`@planner` on an already-completed feature would lose anything, which is the question that
actually surfaced the gap.

### Decision: freeze artifacts into `.harness/reviews/` at two specific checkpoints, not continuously

Rather than making the whole of `.harness/output/` permanent (which would make "scratch"
meaningless — nothing would ever be safely disposable), the fix mirrors exactly two moments:
`route.py init` freezes the approved spec and contracts the instant a run starts; `route.py
decide` mirrors each *scored* iteration's output the instant a verdict is final. **Trade-off**:
anything written between those checkpoints and never reaching a scored verdict (a Generator
mid-iteration, before the Evaluator even runs) is still genuinely ephemeral — and that's fine,
because nothing worth auditing exists yet at that point.

### Insight (the expensive one): verifying a fix against live state is not the same as testing it

Smoke-testing the new archiving code the first time, the test wrote directly into the real
`.harness/output/spec.md` and `sprint-1-contract.md` — which, for the already-completed
`regional-rollup-report` run, were the *only remaining copies* of those files, since they
hadn't been committed anywhere yet. The test's own cleanup step then blanket-deleted the rest
of the scratch directory. The fix that was meant to guarantee nothing gets silently lost
caused exactly that loss, during its own verification. The second and third rounds of
smoke-testing used disposable dummy run names (`smoke-test`, `smoke2`) specifically so this
couldn't happen again — a rule that should have been the default from the first test, not a
correction after the fact.

### Decision: don't reconstruct the lost files and present them as if they were real

Once the loss was discovered, the tempting shortcut was to regenerate `spec.md` and the
contracts for the affected run from what was still visible in the conversation history and
quietly backfill `.harness/reviews/`. Declined: a reconstruction differs from what was actually
approved in ways that can't be fully verified, and silently filling the gap would misrepresent
the one thing this fix exists to make trustworthy — that what's in `reviews/` is exactly what
happened. Disclosed the loss plainly instead and left the decision (accept the gap, or attempt
a labeled reconstruction) to the developer.

### Insight: three independently-planned features sharing a scaffold will collide, and nothing warned about it in advance

`shift-handover-bulk-status`, `regional-rollup-report`, and `planogram-task-template` were each
planned and built as if they were the only change happening to the repository — because, from
each run's point of view, they were: every Planner invocation reads `master` as it exists at
that moment, with no visibility into sibling branches also built from the same point. All three
touch `activities/service.py`; two of the three touch `core/events.py`, `reports/service.py`,
and the activities test files. Merging the second branch into the first needed ten
hand-resolved conflicts; merging the third was deferred entirely at the developer's request
once the first ten made the cost visible. **This wasn't a tooling failure** — `import-linter`,
`ruff`, and `pytest` all passed on each branch individually, exactly as designed. It's a gap one
level up: the harness has rigorous rules for *what a single run is allowed to touch*, and no
concept at all of *other runs that already touched the same thing*.

### Insight: merge conflicts in independently-generated code are usually additive, not contradictory, if you look

Expected the three-way conflicts to require real judgment calls about whose logic should win.
In practice, nearly every conflict was two features adding *different* things to the same
file — a new method here, a new import there — and `git`'s own auto-merge already resolved
the non-conflicting parts correctly in every file; the remaining markers were almost all
"combine both sides," not "choose one." The one genuine judgment call was an add/add conflict
on a test file both branches had independently created with the same name and no overlap in
content — resolved by merging the file, not picking a side. Worth remembering: a bad outcome
from siblings colliding doesn't necessarily mean lost work, if someone takes the time to
reconcile rather than force one branch's version over the other's.

---

## Open threads, not yet resolved

- The retry/escalation path (`CONDITIONAL PASS`, `FAIL` with retry, the no-progress heuristic)
  has never been exercised by a real Generator attempt that needed a second try — only by the
  Day 1 probe, built specifically to fail. Whether the 3-iteration cap and the rubric's
  pass/fail thresholds are well-calibrated for a genuinely imperfect first attempt is still an
  open question.
- No mechanism yet checks for sibling harness branches before planning a new feature — the
  concrete improvement proposed in `REFLECTION.md`, not yet implemented.
- `regional-rollup-report` remains deliberately unmerged, at the developer's request, with its
  conflicts against the current `master` not yet resolved.
