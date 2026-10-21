# Harness run index (appended by the Monitor - one row per sprint, never rewrite rows)

Used for skill-drift detection across runs: a skill whose checks fail in more than one run is
flagged for refinement (see `.harness/agents/monitor.agent.md`).

| run_id | sprint | verdict | iterations | escalated | est. tokens | failed checks (all iters) | drift-flagged skills |
|---|---|---|---|---|---|---|---|
