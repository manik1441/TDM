# Repository Guidelines

## Project Overview
- This is a Python 3.10+ FastAPI proof of concept for agentic Test Data Management.
- The app serves a single-page UI from `static/db_viewer.html`, exposes pipeline and CRUD APIs from `app/main.py`, and dynamically loads generated code from `generated/`.
- The agent pipeline lives in `app/engine/leader.py`; markdown prompts live in `agents/` at the root, Python helpers live in `app/engine/`, and the OpenAI-compatible client lives in `app/llm.py`.

## Common Commands
- Install dependencies: `pip install -r requirements.txt`
- Run the app: `uvicorn app.main:app --reload`
- Windows helper: `run_server.bat`
- Health check once running: `GET http://localhost:8000/api/tdm/health`

## Configuration
- Runtime config is loaded from `config.yaml`.
- Secrets come from `.env`; keep `OPENROUTER_API_KEY` out of commits.
- The default database URL is `sqlite:///./test_data.db`.
- `TDM_CONFIG_PATH` can point to an alternate YAML config.

## Code Style
- Follow `agents/rules.md`: strict type hints for function signatures, `snake_case` for functions/files/variables, `PascalCase` for SQLAlchemy and Pydantic classes, and `UPPER_SNAKE_CASE` for constants.
- API responses should stay structured JSON. Prefer `{"success": true, "data": ...}` or `{"success": false, "error": ...}` for new surfaces.
- Use SQLAlchemy 2.x, FastAPI, Pydantic 2.x, and Faker consistently with existing code.
- Keep comments short and useful; avoid broad rewrites unless the task needs them.

## Generated Files
- `generated/models.py` and `generated/schema_routes.py` are produced by the Generator Agent and imported dynamically. `generator.py` is obsolete because runtime data generation is handled by `app.engine.generic_generator`.
- Generated models must use `from app.db import Base`.
- Generated routes should expose an `APIRouter` named `router` with prefix `/api/tdm`.
- Be careful when editing generated files directly; future pipeline runs may overwrite them.

## Database and API Safety
- Validate table and column names before using them in raw SQL. Existing meta endpoints validate table names first; preserve or improve that pattern.
- Every generated table should include an integer primary-key `id` column.
- Foreign keys should be explicit where relationships exist.

## Testing and Verification
- There is no dedicated test suite in the repo currently.
- For Python syntax checks, use `python -m compileall .` from the repo root.
- For app verification, start Uvicorn and check `/api/tdm/health`, `/`, and relevant `/api/tdm/...` endpoints.

## Git Notes
- In the Codex sandbox, `git status` may fail with Git's dubious ownership protection for this repo. Do not change global Git config unless the user approves.
- Do not revert user changes or generated artifacts unless explicitly asked.
