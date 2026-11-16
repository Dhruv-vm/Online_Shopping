# BASKET Backend

FastAPI modular monolith backend service for BASKET.

## Setup

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Running the server

```bash
uvicorn app.main:app --reload --port 8000
```
