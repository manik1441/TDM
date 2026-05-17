# Agentic AI-Powered Test Data Management (TDM)

This is a Python-based POC for a custom, multi-agent TDM Solution. It features an AI-powered pipeline to generate custom, generic test data environments dynamically from a text prompt! The system is orchestrated by specialized AI agents and managed via a unified SPA command center.

## Tech Stack
* **Language**: Python 3.10+
* **API Generation**: FastAPI & Uvicorn
* **Data Mocking**: Faker
* **LLM Integration**: OpenRouter (OpenAI-compatible architecture)
* **Database ORM**: SQLAlchemy 
* **Database**: SQLite (configured for POC locally)
* **UI**: Unified Single Page Application (HTML/JS/Vanilla CSS/Tailwind)

## Features Included
1. **Agent Pipeline**: Markdown-backed prompt steps plus Lead and Generator Python helpers generate database structures, APIs, and data.
2. **Unified SPA Command Center**: A sleek web UI to input prompts, track real-time agent pipeline status via WebSockets, and perform full CRUD operations on generated tables.
3. **Synthetic Test Data Generation**: Generates massive amounts of structured test data obeying predefined constraints.
4. **Data Provision API**: Dynamically exposed FastAPI endpoints acting as the "get test data" interface for Automation/Performance Tools.
5. **LLM Agnostic**: Configurable to use any OpenAI-compatible provider via OpenRouter.

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env`, then add your OpenRouter API key.

3. Run the application:
```bash
uvicorn app.main:app --reload
```

## Usage

### 1. Unified Command Center
Open your browser while the server is running and navigate to:
**http://localhost:8000/** (or **http://localhost:8000/db-viewer**)

From here you can:
- **Submit Requirements**: Enter your business prompt (e.g., "Library System with Books and Members") and watch the agents build the schema in real-time.
- **Manage Data**: View generated tables, perform CRUD operations, and execute raw SQL natively.

### 2. Fetch Data from Frameworks
The performance testing tools and test automation framework can fetch managed test data from the dynamically generated endpoints.
```bash
# Example generic route
curl.exe -X GET "http://localhost:8000/api/tdm/<your-generated-entity>?limit=50"
```

### 3. Generate / Refresh DB (via API)
To trigger the DB cleanup and inject the dummy test data for your active schema programmatically, run:
```bash
curl.exe -X POST http://localhost:8000/api/tdm/refresh-data
```

## Project Structure
- `app/main.py`: Core FastAPI file exposing the UI, pipeline APIs, and CRUD endpoints.
- `app/engine/leader.py`: Agent pipeline orchestrator.
- `app/db.py`: SQLAlchemy session engine logic.
- `app/config.py`, `app/llm.py`, `app/logger.py`: Shared configuration loader, LLM/prompt loader interface, and logging utilities.
- `app/engine/`: Python helpers for steps that need custom execution logic.
- `agents/`: Agent prompt and rule markdown files (at root level).
- `generated/`: Directory automatically populated with your generated domain folders containing `models.py` and `schema_routes.py`. `generator.py` is obsolete when using `app.engine.generic_generator`.
- `static/`: Contains the Unified SPA Command Center (`db_viewer.html`).
- `config.yaml`: Runtime configuration.
