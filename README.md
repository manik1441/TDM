# Generic AI-Powered Test Data Management (TDM)

This is a Python-based POC for the Custom TDM Solution. It features an AI-powered pipeline to generate custom, generic test data environments dynamically from a text prompt!

## Tech Stack
* **Language**: Python 3.10+
* **API Generation**: FastAPI & Uvicorn
* **Data Mocking**: Faker
* **LLM Integration**: Google Gemini API (`google-genai`)
* **Database ORM**: SQLAlchemy 
* **Database**: SQLite (configured for POC locally)

## Features Included
1. **AI-Powered Prompt Builder**: Provide a business requirement (e.g. "Hospital System with Doctors and Patients") and the LLM will dynamically generate the database structure, logic, and API endpoints!
2. **Clean up DB**: Delete previously used data from DB.
3. **Synthetic Test Data Generation**: Generates massive amounts of structured test data obeying predefined constraints.
4. **Data Provision API**: Dynamically exposed FastAPI endpoints acting as the "get test data" interface for Automation/Performance Tools.
5. **Database Viewer Dashboard**: Embedded web UI to strictly monitor generated tables and run custom SQL natively.

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application (starts API server):
```bash
uvicorn main:app --reload
```

## Usage

### 1. Build Custom Schema via Prompt
You can dynamically rewrite the entire database schema using the power of AI!
1. Open `new_requirement.md` and type your requirements (e.g., "Library System with Books and Members").
2. Set your API Key: `set GEMINI_API_KEY=your_api_key` (Windows cmd)
3. Run the generator script:
```bash
python prompt_builder.py
```
*(Because Uvicorn is running with `--reload`, the server will automatically restart and mount the new features under the hood when the script finishes!)*

### 2. Generate / Refresh DB 
To trigger the DB cleanup and inject the dummy test data for your active schema, run:
```bash
curl.exe -X POST http://localhost:8000/api/tdm/refresh-data
```

### 3. Fetch Data from Frameworks
The performance testing tools and test automation framework can fetch managed test data from the dynamically generated endpoints.
```bash
# Example generic route
curl.exe -X GET "http://localhost:8000/api/tdm/<your-generated-entity>?limit=50"
```

### 4. Integrated Database Viewer
A beautiful, sleek database dashboard is built natively into the API to let you easily visualize any generated tables, verify test data distribution, and even execute your own custom SQL dynamically.

Open your browser while the server is running and navigate to:
**http://localhost:8000/db-viewer**

### 5. Swagger UI Documentation
FastAPI provides automatic interactive API documentation via Swagger UI. You can use it to explore and test the dynamically generated test data endpoints.

Open your browser while the server is running and navigate to:
**http://localhost:8000/docs**

## Project Structure
- `prompt_builder.py`: AI script that reads your requirements and overwrites backend logic.
- `new_requirement.md`: Your prompt definition file.
- `models.py`: SQLAlchemy schemas representing the Database structure *(auto-generated)*.
- `schema_routes.py`: Dynamic FastAPI endpoints representing your schema *(auto-generated)*.
- `generator.py`: TDM rules, Faker generation logic, and distributions *(auto-generated)*.
- `main.py`: Core FastAPI file acting as the generic application orchestrator.
- `database.py`: SQLAlchemy session engine logic.
- `db_viewer.html`: SPA frontend that renders the database dashboard.
