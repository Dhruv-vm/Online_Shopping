# BASKET — Two-Developer Git and Antigravity Workflow

## 1. Repository branches

```text
main
  └── integration
        ├── feature/catalogue-search
        ├── feature/cart-checkout
        ├── feature/kafka-outbox
        └── feature/one-approved-differentiator
```

- `main`: stable, demo-ready code only.
- `integration`: shared integration branch.
- `feature/*`: isolated task branches.

Protect `main` and `integration` where GitHub settings allow. Require PR review and passing checks before merging.

## 2. Separate working directories

Two agents must not edit the same working tree concurrently.

If both developers use the same computer, use Git worktrees:

```bash
git clone YOUR_REPOSITORY_URL basket
cd basket
git checkout integration
git pull origin integration

git worktree add ../basket-dev-a -b feature/catalogue-search integration
git worktree add ../basket-dev-b -b feature/cart-checkout integration
```

Open `basket-dev-a` and `basket-dev-b` as separate Antigravity workspaces.

If developers use separate computers, each should have their own clone and branch.

## 3. Feature branch routine

```bash
git fetch origin
git checkout integration
git pull --ff-only origin integration
git checkout -b feature/short-feature-name

# implement and test
git status
git diff --check
git add path/to/your/changes
git commit -m "feat: implement short feature"
git push -u origin feature/short-feature-name
```

Open a PR from the feature branch into `integration`. Include scope, screenshots/API examples, tests, migration notes, and known limitations.

## 4. Before starting a task

- Confirm task owner in `TASK_BREAKDOWN.md`.
- Read `AGENT_HANDOFF.md` for open proposals/blockers.
- Check whether your work touches shared contracts.
- Agree on API request/response shapes before parallel frontend/backend work.
- Create a small implementation plan and list expected files.

## 5. During work

- Commit in small logical units.
- Pull integration changes regularly; rebase only your own feature branch.
- Do not force-push shared branches.
- Do not commit generated build folders, `.env`, credentials, or unrelated formatting churn.
- If blocked by another module, use a stub only when its contract is agreed and clearly marked as a temporary integration boundary.

## 6. Pull request checklist

- [ ] Scope matches assigned task.
- [ ] No unrelated files changed.
- [ ] Tests added/updated and passing.
- [ ] Lint/type checks pass.
- [ ] Migration is coordinated and tested.
- [ ] API contract is updated if needed.
- [ ] No secrets or personal data.
- [ ] Error/loading/empty states handled.
- [ ] Known limitations disclosed.
- [ ] Reviewer understands how to verify the change.

## 7. Integration owner

Assign one developer as integration owner. This person:
- Owns `integration` branch health.
- Coordinates shared files and migrations.
- Reviews PRs and resolves conflicts.
- Runs the full integration test path.
- Decides whether a feature is ready for `main`.

The integration owner is not allowed to bypass tests or silently discard the other developer's work.
