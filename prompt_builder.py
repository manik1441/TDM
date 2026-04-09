import os
import json
from google import genai
from google.genai import types

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable. If you do not have one, you can acquire it from Google AI Studio.")
        return

    with open("new_requirement.md", "r") as f:
        user_prompt = f.read()

    print("Generating schema, models, generator script and routes via Gemini API. This may take 10-20 seconds...")
    client = genai.Client()
    
    system_prompt = """
You are an expert Python Backend Developer. 
Return ONLY valid JSON that parses exactly into Python `json.loads()`. The JSON must contain 3 string keys: "models_py", "generator_py", and "schema_routes_py".
Each key must be a string containing raw formatted Python code for that specific file. DO NOT WRAP WITH MARKDOWN BACKTICKS INSIDE THE VALUE.
No preamble, no markdown formatting block covering the overall JSON.

1. `models_py`: Define SQLAlchemy models using `from database import Base`. Provide all necessary columns and relationships.
2. `generator_py`: Must contain `generate_base_data(db, scale_factor=1.0)` and `generate_transactional_data(db, scale_factor=1.0)` functions which generate dummy data using `faker`. Needs to import the models from `models`. Example: `import faker` and `fake = Faker()`. `db.add_all()` elements and commit. It needs to reflect realistic business logic matching the user prompt.
3. `schema_routes_py`: An APIRouter for FastAPI with `GET` and optionally `POST` endpoints to serve the generic data generated above. MUST contain `router = APIRouter()`. Use `from fastapi import APIRouter, Depends` and `from sqlalchemy.orm import Session`, `from database import get_db`. Import the generated models from `models`. Provide at least one route over the primary models.

Output format STRICTLY:
{
  "models_py": "import...",
  "generator_py": "import...",
  "schema_routes_py": "import..."
}
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json"
        )
    )

    try:
        data = json.loads(response.text)
        
        with open("models.py", "w") as f:
            f.write(data["models_py"])
        with open("generator.py", "w") as f:
            f.write(data["generator_py"])
        with open("schema_routes.py", "w") as f:
            f.write(data["schema_routes_py"])
            
        print("Success! Overwrote models.py, generator.py, and schema_routes.py.")
        print("If you are running `uvicorn main:app --reload`, the server will automatically restart with your new generic endpoints!")
    except Exception as e:
        print("Error parsing the JSON from Gemini:", e)
        print("Response received:", response.text)

if __name__ == "__main__":
    main()
