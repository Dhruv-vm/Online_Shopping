# BASKET — Mandatory Antigravity Agent Rules

These rules apply to **both developers and every Antigravity agent session**. Read this file before editing code.

## 1. Operating model

- Google Antigravity is the only coding IDE/agent environment for this project.
- ChatGPT is used by the developers for planning, prompt preparation, architecture review, debugging, and quality review.
- Each developer uses a separate Git working directory and a separate feature branch.
- Never allow two agents to edit the same working directory at the same time.
- Never assume another agent's uncommitted changes are safe to overwrite.

## 2. Read before coding

At the start of every task:
1. Read `README.md`.
2. Read `PROJECT_CHARTER.md`, `ARCHITECTURE.md`, and this file.
3. Read the relevant API/data contract documents.
4. Read the latest entries in `AGENT_HANDOFF.md` and `DECISIONS.md`.
5. Inspect the existing code before proposing replacements.
6. Report the files/modules you intend to touch and any dependencies.

## 3. Scope discipline

- Implement only the assigned task.
- Do not build unrelated features.
- Do not rewrite working modules just to match personal preferences.
- Do not change the stack or add dependencies without approval.
- Do not invent provider APIs, environment variables, database fields, or endpoints.
- If a requirement is unclear, ask or record a blocking question in `AGENT_HANDOFF.md`.
- If the task is too large, propose a smaller complete vertical slice.

## 4. File ownership

Before implementation, the team must fill in module ownership in `TASK_BREAKDOWN.md`.

- Do not edit another developer's owned feature files without explicit coordination.
- Shared files include: database base/config, authentication, global settings, shared API client, common schemas, event envelope, Alembic migration history, root configuration, and CI workflows.
- Only the designated integration owner may merge shared-contract changes.
- If a shared file must change, announce the proposed change in `AGENT_HANDOFF.md` before editing and wait for agreement.
- Never create competing Alembic heads. Coordinate migrations and merge/rebase them deliberately.

## 5. Code quality

- Prefer readable, typed, small functions and explicit names.
- Keep route handlers thin; put business logic in service functions.
- Use Pydantic request/response schemas.
- Use SQLAlchemy 2.x patterns consistently.
- Use TypeScript strict mode; avoid `any` unless justified and isolated.
- Reuse existing components and conventions.
- Handle loading, empty, success, and error states.
- Validate all untrusted input.
- Add tests for business rules and failure paths.
- Do not suppress exceptions or return fake success responses.
- No placeholder buttons that appear functional but do nothing.
- No hard-coded secrets, real customer data, or production credentials.
- Do not leave `TODO`, `pass`, mocked data, or disabled checks in a feature and claim it is complete.

## 6. AI safety and business authority

- AI may explain, classify, summarize, or propose.
- Backend code decides authorization, price, inventory, quote validity, payment state, and order transitions.
- Never let an LLM write arbitrary SQL or directly mutate critical tables.
- Every tool exposed to an AI assistant must have narrow input validation, authorization, and auditable server-side execution.

## 7. Git rules

- Never commit directly to `main`.
- Do not push directly to `integration` unless explicitly assigned as integration owner.
- Use a descriptive feature branch.
- Pull/rebase from the agreed base before opening a PR.
- Commit focused changes with conventional messages.
- Do not force-push shared branches.
- Do not commit `.env`, credentials, generated secrets, or unrelated files.
- Do not merge your own PR unless the team has agreed that you are the integration owner and review is complete.

## 8. Required completion report

At the end of every task, report:
1. What was implemented.
2. Files created/changed.
3. API routes/contracts added or changed.
4. Database migration(s), if any.
5. Tests run and exact results.
6. Manual verification performed.
7. Known limitations and unimplemented cases.
8. Any shared-contract changes requiring review.
9. Suggested commit message and branch name.

Do not say "complete" unless the relevant quality gates pass.
