Client Context
==============
Assume you are a Solution Architect , embedded with a retail client whose eight-developer squad is building the StoreOps API. The client's CTO has approved AI-assisted development using Claude Code. The engineering standards team has concerns: in a prior experiment, AI-generated code produced four specific failure modes:
 1. Direct imports from another module's repository, bypassing the agreed service boundary and event bus
 2. Raw Error throws in service methods, bypassing the project's typed AppError hierarchy 
 3. Tests that asserted HTTP status codes but did not verify business rule compliance 
 4. Missing event bus integration — state changes written directly to sibling module repositories

The standards team will not support the Claude Code rollout without a harness that prevents these failure modes from reaching main.
A harness should be built to address this.


A development harness should solve this by wrapping AI code generation in a structured orchestration layer: agents with defined roles, skill files that provide feedforward context before each agent acts, and an evaluation loop that applies checks before output is accepted. The result is governed, standards-driven, AI-accelerated development.

The Harness
===========

The harness has four components: Planner, Generator, Evaluator, and Monitor. Once the developer approves the Planner's spec, the Generator and Evaluator loop runs autonomously — the developer does not manually trigger each iteration. Claude Code should drive this loop, with the developer re-entering only at escalation points. The Monitor records outcomes after every sprint run, providing the observability data needed to detect skill file drift and tune the harness over time.

Component | Role | What it Produces|
Planner| Decomposes requirements | spec.md + sprint contracts with GIVEN/WHEN/THEN acceptance criteria |
Generator | Implements sprint contracts | Code, tests, and generator-summary.md (AC self-check table, files changed, known gaps) |

Evaluator | Reviews Generator output | Structured verdict (PASS / CONDITIONAL PASS / FAIL) with file-level and line-level feedback in evaluator-feedback.md |

Monitor | Records sprint run outcomes for observability and skill file improvement | run-log.md per sprint: iterations used, verdict, escalation flag, estimated token cost, and quality trend notes — archived to .harness/reviews/ |


- CLAUDE.md is the root orchestrator. 
- It reads the Evaluator's verdict and decides the next action: advance to the next sprint on PASS, send feedback back - to the Generator on FAIL, or escalate to the developer after a maximum of three iterations. 
- The Monitor runs after each sprint verdict — it reads evaluator-feedback.md and writes a structured "run-log.md" to ".harness/reviews/"
This archive is the governance audit trail and the primary input for detecting which skill files need refinement.


CLAUDE.md
==========
- Define the agents (by referencing the .harness/agents/*.agent.md files), the orchestration sequence, and the routing logic.
- The Planner is invoked with a single developer prompt (e.g., '@planner Add shift handover bulk update to tasks'). Claude Code then drives the - -Generator/Evaluator loop autonomously, writing and reading handoff files in .harness/output/ to pass context between agents.
The developer's only active steps are: 
	(1) invoke the Planner with a feature prompt, and 
	(2) type APPROVED after reviewing spec.md. After that, Claude Code runs the loop until all sprints PASS or an escalation occurs.



Harness Components to be built
==============================

CLAUDE.MD - Orchestrator
- The root CLAUDE.md is the orchestration brain of the harness. It must define:
- The entry prompt format a developer uses to start a harness run
- The agent files it references and how each is invoked
- The sequence: Planner → spec.md produced → AWAITING APPROVAL marker → developer types APPROVED → Generator/Evaluator loop begins
-  Routing logic: how the orchestrator reads the verdict in evaluator-feedback.md and decides next action (next sprint, retry Generator, or escalate)
-  The maximum iteration count per sprint before escalating — and what the escalation output looks like (e.g., a written escalation notice in .harness/output/escalation.md naming the sprint, iteration count, and blocking issue)
- Context scoping strategy: how context is reset or bounded between agent invocations to prevent context window degradation across long runs
- CI/CD relationship: a note on how the Evaluator's automated checks (lint, type check, test runner) relate to existing pipeline gates — does the harness precede, replace, or feed into CI checks
 |

Agent Files
Three agent definition files in .harness/agents/. Each specifies the agent's responsibility, the skill files it reads before acting, and the handoff file it writes.


File | Reads (minimum) | Produces
planner.agent.md | app-context, architecture-principles, sprint-decomposition | spec.md (with STATUS: AWAITING APPROVAL marker), sprint-N-contract.md




generator.agent.md | app-context, architecture-principles + stack-specific skills | Code in src/, generator-summary.md (AC self-check table, files changed, known gaps)|

evaluator.agent.md | architecture-principles, how-to-review + evaluation criteria skills | evaluator-feedback.md with structured verdict, per-check results, and file+line feedback on failures |

monitor.agent.md | app-context (reads evaluator-feedback.md + generator-summary.md from completed sprint)| run-log.md archived to .harness/reviews/: sprint ID, verdict, iterations used, escalation flag, estimated token cost, quality trend notes |


Skill Files
===========
Skill files are feedforward guides — markdown files each agent reads before acting. Produce at least 6, covering:
• Shared foundation (required for all agents): app-context, architecture-principles
• Generator-specific (minimum 2): e.g., coding-conventions, component-patterns, api-integration, how-to-test
• Evaluator-specific (minimum 2): e.g., how-to-review, grading criteria files

Skill files must reflect the current project. A generic file that could apply to any codebase will not pass evaluation.
Each file should encode decisions specific to the project — module boundary rules, agreed error-handling contracts, test coverage thresholds, and stack-specific automated check commands.


Skill file format
-----------------
Each skill file is a plain markdown file (SKILL.md) inside a named subdirectory under .harness/skills/.
Structure it with a clear purpose statement at the top, followed by specific rules, examples, or reference material.
Length should match the complexity of what the agent needs — a coding-conventions file for a typed language may run 2–4 pages; an app-context file may be shorter.



Evaluation Framework
====================

The Evaluator is where non-deterministic systems design competency is most directly tested. It must implement structured graded evaluation across at least two dimensions. Each dimension must define:
• A weight (all dimensions must sum to 100%)
• Hard gate conditions — specific failures that cause an immediate FAIL verdict regardless of other scores. These must be deterministic: given the same check result, the verdict is always the same.
• A checklist of specific checks with explicit pass/fail criteria
• How the Evaluator handles the inherent variability of LLM-generated code: what it checks, how it converts variable output into a binary per-check result, and what the fallback is when the Evaluator's own output is ambiguous

It is strongly recommended that at least one hard gate per dimension corresponds to an automated tool check — a linter, type checker, test runner, or dependency analyser.
Automated checks are deterministic by design and prevent verdict variability caused by LLM assessor leniency.

Module Structure
================

Module | Retail responsibility | Key types/Entities
====================================================
activities | Manage operational activities — restocking runs, planogram resets, compliance checks, and general store tasks | Task, TaskStatus (TODO | IN_PROGRESS | DONE | BLOCKED), TaskPriority (LOW | MEDIUM | HIGH | CRITICAL), TaskCategory (RESTOCKING | PLANOGRAM | AUDIT | COMPLIANCE | GENERAL) |
programmes | Manage store programmes and their staff membership — seasonal rollouts, compliance drives, store refits | Project, ProjectMember, ProjectRole (STORE_MANAGER | DEPARTMENT_LEAD | ASSOCIATE)|

staff | Store staff registration, authentication, and profile management | User, UserProfile, StaffRole (REGIONAL_MANAGER | STORE_MANAGER | DEPARTMENT_LEAD | ASSOCIATE), AuthToken|

alerts | Deliver in-app alerts triggered by operational events — inventory flags, SLA breaches, and shift handover prompts | Notification, NotificationChannel (IN_APP | EMAIL), NotificationStatus, AlertType

reports | Generate store and regional performance summaries — task completion rates, overdue counts by department, regional rollups on demand | Report, ReportType (STORE_SUMMARY | REGIONAL_ROLLUP | DEPARTMENT_PERFORMANCE), ReportStatus (PENDING | READY | FAILED)

Each module follows a strict three-layer model: Routes (HTTP + validation) → Service (business logic) → Repository (data access). Cross-module communication follows two rules: modules may call another module's service layer for read-only lookups; event-driven side effects (e.g., firing an SLA_BREACH notification when a CRITICAL task becomes overdue, or triggering a STORE_SUMMARY report when a programme closes) are raised via an event bus, never by direct service-to-service import. The reports module is read-only — it aggregates data across activities, programmes, and staff but never writes to those modules.

What the Harness should govern
==============================

The harness will be run against the StoreOps codebase. During the demonstration run, we should be able to invoke the Planner with a retail operations feature prompt — asking the harness to add a new capability to StoreOps. Suggested features:
• Add shift handover bulk update — PATCH /api/activities/bulk-status allowing outgoing shift staff to mark multiple operational activities as DONE or BLOCKED in a single request, with partial failure handling and an audit entry per updated task
• Add SLA breach alerting — when a HIGH or CRITICAL task passes its due date without reaching DONE, automatically fire a SLA_BREACH notification to the assigned Department Lead and escalate to STORE_MANAGER if unresolved after a configurable grace period
• Add regional rollup report — GET /api/reports/region/:id aggregating task completion rates, overdue counts by TaskCategory, and blocked task lists across all stores in the region; triggers a REGIONAL_ROLLUP Report record via the event bus
• Add planogram task template — POST /api/programmes/:id/templates to clone a standard set of PLANOGRAM tasks into a new store programme, applying department assignments and default priorities from the template definition


The harness should generate correctly layered new code (routes → service → repository), tests that meet coverage thresholds, and pass all automated checks without manual intervention. After the harness run, the new feature must be demonstrable through the running application — call the new endpoint via curl or Postman and show a successful response.


Architecture Rules the Evaluator Must Enforce
==============================================

These are the non-negotiable StoreOps architecture rules. The evaluation hard gates and skill files must encode these specifically — not as generic principles. Each rule maps directly to one of the four failure modes identified in the client context.

Rule | What it prohibits | How your Evaluator checks it |
Module boundary | No module may import directly from another module's repository. Cross-module reads go through the target module's service layer only. | Automated: depcruiser or equivalent dependency analyser — zero cross-module repository imports|

Event bus only | Side effects that cross module boundaries must be raised via the event bus — never by direct service-to-service import. | LLM-assessed: Evaluator checks that EventBus.emit() is used for cross-module triggers — no direct NotificationService or ReportService imports |

Error contract | No raw Error throws in services or routes. All errors must use the AppError typed hierarchy (code, message, statusCode). | Automated (linter rule) + LLM-assessed: zero raw throw new Error() in services or routes|


Layer separation | Routes → Service → Repository — no skipping. Routes must not contain business logic; repositories must not call external services. | LLM-assessed: Generator summary references correct layer for each changed file; Evaluator checks no HTTP logic in repositories

Read-only reports | The reports module aggregates data from activities, programmes, and staff — it never writes to those modules. | LLM-assessed: Evaluator verifies no write operations originate from the reports module |


Minimum automated test coverage thresholds to apply
Scope | Coverage Threshold
Service layer | 80% line coverage minimum
Route / controller layer | 70% line coverage minimum
Shared utilities | 60% line coverage minimum
Overall project | 70% line coverage minimum




