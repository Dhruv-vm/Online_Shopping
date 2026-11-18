#!/usr/bin/env bash
# ==============================================================================
# BASKET — Quick Developer Setup Script
# Bootstraps Backend venv (uv) and Frontend dependencies (npm).
# ==============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Bootstrapping BASKET Monorepo ==="

# Backend Setup
echo ""
echo "--- 1. Setting up Backend (Python 3.12 + uv) ---"
cd "$REPO_ROOT/backend"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment with uv..."
    uv venv --python 3.12 .venv
fi

source .venv/bin/activate
echo "Installing backend dependencies..."
uv pip install -e ".[dev]"

if [ ! -f ".env" ]; then
    echo "Creating backend/.env from .env.example..."
    cp .env.example .env
fi

# Frontend Setup
echo ""
echo "--- 2. Setting up Frontend (Node + npm) ---"
cd "$REPO_ROOT/frontend"
echo "Installing frontend dependencies..."
npm install

if [ ! -f ".env.local" ]; then
    echo "Creating frontend/.env.local from .env.example..."
    cp .env.example .env.local
fi

echo ""
echo "=== Bootstrap Complete ==="
echo "To start Backend:  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "To start Frontend: cd frontend && npm run dev"
