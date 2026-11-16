# BASKET — Project Control Centre

BASKET is a multi-category online retail platform for an Indian retail chain. This repository is designed for a two-developer team working exclusively in **Google Antigravity**, with ChatGPT used for architecture, prompt preparation, reviews, and debugging.

## Read these first

1. [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) — product scope and non-negotiable priorities.
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) — system boundaries and technical architecture.
3. [`AGENT_RULES.md`](AGENT_RULES.md) — mandatory instructions for both Antigravity agents.
4. [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — the shared communication log between developers/agents.
5. [`DEVELOPMENT_WORKFLOW.md`](DEVELOPMENT_WORKFLOW.md) — Git branches, integration, and daily workflow.
6. [`QUALITY_GATES.md`](QUALITY_GATES.md) — definition of done and release gates.
7. [`TASK_BREAKDOWN.md`](TASK_BREAKDOWN.md) — suggested ownership and implementation sequence.

## Source of truth

- Product scope: `PROJECT_CHARTER.md`
- Architecture: `ARCHITECTURE.md`
- Shared interfaces: `API_CONTRACTS.md`
- Data ownership: `DATA_MODEL.md`
- Decisions: `DECISIONS.md`
- Cross-agent coordination: `AGENT_HANDOFF.md`

If two documents conflict, stop and record the conflict in `AGENT_HANDOFF.md`. Do not silently choose one. The integration owner resolves it and records the decision in `DECISIONS.md`.

## Quality principle

**A small, complete, tested, demonstrable vertical slice is better than many unfinished features.** Mandatory commerce flow and real use of PostgreSQL, Kafka, and OpenSearch take priority over optional AI features.
