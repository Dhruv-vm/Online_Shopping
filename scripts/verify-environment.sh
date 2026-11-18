#!/usr/bin/env bash
# ==============================================================================
# BASKET — Environment and Foundation Verification Script
# Validates both Backend and Frontend dependencies, quality gates, and configurations.
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== BASKET Foundation Verification ==="
echo "Repository: $REPO_ROOT"
echo ""

ERRORS=0

# 1. Git Verification
echo "--- 1. Checking Git Repository ---"
if [ -d "$REPO_ROOT/.git" ]; then
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "None")
    echo "✓ Git initialized on branch: $CURRENT_BRANCH"
    echo "✓ Remote origin: $REMOTE_URL"
else
    echo "✗ Git not initialized!"
    ERRORS=$((ERRORS + 1))
fi

# 2. Python & Backend Verification
echo ""
echo "--- 2. Checking Backend Environment ---"
if [ -d "$REPO_ROOT/backend/.venv" ]; then
    echo "✓ Backend virtual environment found at backend/.venv"
    source "$REPO_ROOT/backend/.venv/bin/activate"
    PYTHON_VER=$(python --version)
    echo "✓ Python runtime: $PYTHON_VER"

    echo "Running backend lint check (ruff)..."
    ruff check "$REPO_ROOT/backend"
    ruff format --check "$REPO_ROOT/backend"
    echo "✓ Ruff checks passed."

    echo "Running backend test suite (pytest)..."
    (cd "$REPO_ROOT/backend" && pytest -v)
    echo "✓ Pytest suite passed."

    echo "Verifying Alembic migration discovery..."
    (cd "$REPO_ROOT/backend" && alembic heads)
    echo "✓ Alembic discovery passed."
else
    echo "✗ Backend virtualenv not found at backend/.venv! Run: cd backend && uv venv --python 3.12 .venv && uv pip install -e \".[dev]\""
    ERRORS=$((ERRORS + 1))
fi

# 3. Node & Frontend Verification
echo ""
echo "--- 3. Checking Frontend Environment ---"
if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node -v)
    echo "✓ Node.js: $NODE_VER"
else
    echo "✗ Node.js not found in PATH!"
    ERRORS=$((ERRORS + 1))
fi

if [ -d "$REPO_ROOT/frontend/node_modules" ]; then
    echo "✓ Frontend node_modules found."
    echo "Running TypeScript type check..."
    (cd "$REPO_ROOT/frontend" && npm run type-check)
    echo "✓ TypeScript type check passed."

    echo "Running production build..."
    (cd "$REPO_ROOT/frontend" && npm run build)
    echo "✓ Frontend production build passed."
else
    echo "! Frontend node_modules not yet installed. Run: cd frontend && npm install"
fi

echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo "✓ ALL VERIFICATION GATES PASSED CLEANLY"
else
    echo "✗ FAILED WITH $ERRORS ERROR(S)"
    exit 1
fi
echo "=========================================="
