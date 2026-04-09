from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import engine, Base, get_db
import generator

# Import models dynamically so metadata is registered to Base before create_all
import models 

# Create DB Schema
Base.metadata.create_all(bind=engine)

app = FastAPI(title="TDM POC API", description="Provides endpoints to fetch synthetic test data.")

@app.post("/api/tdm/refresh-data")
def refresh_data(db: Session = Depends(get_db)):
    """
    Deletes all previously used test data and regenerates new test data.
    """
    # Delete previously used data

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    generator.generate_base_data(db, scale_factor=0.1)

    generator.generate_transactional_data(db, scale_factor=0.1)
    
    return {"message": "Data successfully refreshed and injected."}

try:
    import schema_routes
    app.include_router(schema_routes.router)
except ImportError:
    print("No schema_routes found, skipping custom dynamic routes.")


# --- DB VIEWER ENDPOINTS ---

@app.get("/db-viewer", response_class=FileResponse, include_in_schema=False)
def serve_db_viewer():
    """Serves the isolated Single-Page DB viewer HTML file"""
    return FileResponse("db_viewer.html")

@app.get("/api/tdm/meta/tables")
def get_tables(db: Session = Depends(get_db)):
    """Returns a list of all tables in the SQLite database"""
    result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"))
    tables = [row[0] for row in result.all()]
    return {"tables": tables}

@app.get("/api/tdm/meta/table/{table_name}")
def get_table_data(table_name: str, limit: int = 500, db: Session = Depends(get_db)):
    """Fetches columns and row data for a requested table"""
    # Simple validation to prevent basic SQL injection on table names
    tables_res = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    valid_tables = [r[0] for r in tables_res.all()]
    if table_name not in valid_tables:
        return {"error": "Invalid table name", "columns": [], "rows": []}
        
    result = db.execute(text(f"SELECT * FROM {table_name} LIMIT :limit"), {"limit": limit})
    columns = list(result.keys())
    rows = [dict(row) for row in result.mappings().all()]
    return {"columns": columns, "rows": rows}

class SQLQuery(BaseModel):
    query: str

@app.post("/api/tdm/meta/query", include_in_schema=False)
def execute_custom_query(sql: SQLQuery, db: Session = Depends(get_db)):
    """Executes raw SQL query from the frontend and returns data"""
    try:
        result = db.execute(text(sql.query))
        
        if sql.query.lstrip().upper().startswith("SELECT") or sql.query.lstrip().upper().startswith("PRAGMA"):
            columns = list(result.keys())
            rows = [dict(row) for row in result.mappings().all()]
            return {"columns": columns, "rows": rows}
        else:
            db.commit()
            return {"columns": ["Result"], "rows": [{"Result": f"Execute OK. Rows affected: {result.rowcount}"}]}
    except Exception as e:
        return {"error": str(e), "columns": [], "rows": []}
