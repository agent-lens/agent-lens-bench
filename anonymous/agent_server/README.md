# Agent Engine Server

Provides access to Claude Code (and other CLI agents) through a simple REST API. You can plug this API into the benchmark in place of an IDE-based agents to run the benchmark against Claude Code, Codex, and others.

Each agentic CLI has a separate route with the same API:
- `/mock` returns mock responses
- `/claude` runs Claude Code

There is a useful `/claude/health` endpoint which makes a simple ping request to Claude Code so you can check if CLI agent is available.
For complete API reference, see `/docs` endpoint.

## How to start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Server runs on `http://127.0.0.1:8000` by default.

Optional request logging:
- Default (no files saved): `uvicorn main:app --reload`
- Save Claude request/response JSON files: `CLAUDE_DUMPS_DIR=logs/claude uvicorn main:app --reload`
