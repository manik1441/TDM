"""
TDM API Server â€” Core FastAPI application.
No Swagger docs. Serves the unified SPA, pipeline APIs, CRUD endpoints, and dynamic schema routes.
"""

import sys
import importlib
import asyncio
import json
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.db import engine, Base, get_db
from app.logger import get_logger
from app.engine import pipeline_watcher
from app.engine import lead as lead_agent

logger = get_logger(__name__)

_project_root = Path(__file__).parent.parent


def _quote_identifier(name: str) -> str:
    """Quote a SQL identifier safely for SQLite / SQLAlchemy text queries."""
    if not isinstance(name, str) or not name:
        raise ValueError('Invalid identifier')
    if '"' in name or ';' in name or '--' in name:
        raise ValueError('Invalid identifier characters')
    return f'"{name}"'


# --- Dynamic model/route loading ---

def get_active_domain_slug() -> str:
    """Read the active domain slug from generated/active_domain.json, falling back to 'general'."""
    active_json_path = _project_root / "generated" / "active_domain.json"
    if active_json_path.exists():
        try:
            with open(active_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("active_domain", "general")
        except Exception:
            pass
    return "general"


def get_active_domain_name() -> str:
    slug = get_active_domain_slug()
    domain_json_path = _project_root / "generated" / slug / "domain.json"
    if domain_json_path.exists():
        try:
            with open(domain_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("domain", slug.replace("_", " ").title())
        except Exception:
            pass
    return slug.replace("_", " ").title()


def _load_generated_modules():
    """Attempt to load generated models and routes for the active domain."""
    slug = get_active_domain_slug()
    generated_dir = _project_root / "generated" / slug
    if not generated_dir.exists():
        return

    # Add active domain dir to sys.path so 'from models import ...' works inside generated files
    gen_str = str(generated_dir)
    if gen_str not in sys.path:
        sys.path.insert(0, gen_str)
    elif sys.path[0] != gen_str:
        sys.path.remove(gen_str)
        sys.path.insert(0, gen_str)

    _remove_obsolete_generator_py_files()

    try:
        if (generated_dir / "models.py").exists():
            Base.metadata.clear()
            Base.registry.dispose()
            if "models" in sys.modules:
                del sys.modules["models"]
            importlib.import_module("models")
            logger.info(f"Loaded generated models.py for domain '{slug}'")
    except Exception as e:
        logger.warning(f"Could not load generated models.py: {e}")

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created from generated models")
    except Exception as e:
        logger.warning(f"Could not create tables: {e}")


def _remove_obsolete_generator_py_files():
    """Delete obsolete generated generator.py files that are not used by generic_generator."""
    generated_root = _project_root / "generated"
    if not generated_root.exists():
        return

    for item in generated_root.iterdir():
        if item.is_dir():
            obsolete_file = item / "generator.py"
            if obsolete_file.exists():
                try:
                    obsolete_file.unlink()
                    logger.info(f"Removed obsolete generated file: {obsolete_file}")
                except OSError as exc:
                    logger.warning(f"Could not remove obsolete generator.py: {exc}")

    root_obsolete = generated_root / "generator.py"
    if root_obsolete.exists():
        try:
            root_obsolete.unlink()
            logger.info(f"Removed obsolete generated file: {root_obsolete}")
        except OSError as exc:
            logger.warning(f"Could not remove obsolete generator.py: {exc}")


def _mount_generated_routes(app: FastAPI):
    """Mount schema_routes from the active generated directory."""
    slug = get_active_domain_slug()
    generated_dir = _project_root / "generated" / slug
    if not generated_dir.exists():
        return

    try:
        if (generated_dir / "schema_routes.py").exists():
            if "schema_routes" in sys.modules:
                importlib.reload(sys.modules["schema_routes"])
                mod = sys.modules["schema_routes"]
            else:
                mod = importlib.import_module("schema_routes")

            if hasattr(mod, "router"):
                app.include_router(mod.router)
                logger.info(f"Mounted generated schema_routes for domain '{slug}'")
    except Exception as e:
        logger.warning(f"Could not mount schema_routes: {e}")


# --- App ---

app = FastAPI(
    title="TDM API",
    docs_url=None,      # Swagger removed
    redoc_url=None,      # ReDoc removed
    openapi_url=None,    # OpenAPI schema removed
)

_load_generated_modules()
_mount_generated_routes(app)
app.mount("/static", StaticFiles(directory=str(_project_root / "static")), name="static")


# --- WebSocket manager for pipeline status ---

class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        if session_id not in self.connections:
            self.connections[session_id] = []
        self.connections[session_id].append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        if session_id in self.connections:
            self.connections[session_id].remove(ws)

    async def broadcast(self, session_id: str, data: dict):
        if session_id in self.connections:
            for ws in self.connections[session_id]:
                try:
                    await ws.send_json(data)
                except Exception:
                    pass

ws_manager = ConnectionManager()


# --- Pipeline Endpoints ---

class PromptInput(BaseModel):
    prompt: str

class StructuredInput(BaseModel):
    session_id: str
    answers: dict


@app.post("/api/generate")
@app.post("/api/tdm/generate")
def start_generation(body: PromptInput):
    """Start the agent pipeline from a user prompt."""
    result = pipeline_watcher.start_pipeline(body.prompt)
    return result


@app.post("/api/generate/structured")
@app.post("/api/tdm/generate/structured")
def continue_generation(body: StructuredInput):
    """Continue the pipeline with structured form answers. Runs full pipeline."""
    result = pipeline_watcher.continue_pipeline(body.session_id, body.answers)
    return result


@app.get("/api/pipeline/status/{session_id}")
@app.get("/api/tdm/pipeline/status/{session_id}")
def get_pipeline_status(session_id: str):
    """Get the current status of a pipeline session."""
    session = pipeline_watcher.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.websocket("/ws/pipeline/{session_id}")
async def pipeline_websocket(websocket: WebSocket, session_id: str):
    """WebSocket for real-time pipeline status updates."""
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            # Keep connection alive, listen for client messages
            data = await websocket.receive_text()
            # Client can send "status" to get current state
            if data == "status":
                session = pipeline_watcher.get_session(session_id)
                if session:
                    await websocket.send_json(session)
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)


# --- Data Refresh Endpoint ---

@app.post("/api/tdm/refresh-data")
def refresh_data(scale_factor: float = 0.1, db: Session = Depends(get_db)):
    """Drops all tables, recreates them, and regenerates test data."""
    # Reload models to make sure newly generated schemas are registered in SQLAlchemy
    _load_generated_modules()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    try:
        from app.engine import data_generator
        data_generator.generate_universal_data(db, scale_factor=scale_factor)

        # Count generated tables
        tables_count_res = db.execute(text(
            "SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ))
        table_count = tables_count_res.scalar() or 0

        return {"message": f"Data successfully refreshed and injected. {table_count} tables created."}
    except Exception as e:
        logger.error(f"Data refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- DB Viewer / SPA ---

@app.get("/", response_class=FileResponse, include_in_schema=False)
@app.get("/db-viewer", response_class=FileResponse, include_in_schema=False)
def serve_ui():
    """Serves the unified SPA."""
    return FileResponse(str(_project_root / "static" / "db_viewer.html"))


# --- DB Meta Endpoints ---

@app.get("/api/tdm/meta/tables")
def get_tables(db: Session = Depends(get_db)):
    """Returns a list of all tables in the database with their row counts."""
    result = db.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ))
    tables = []
    for row in result.all():
        table_name = row[0]
        try:
            quoted_table = _quote_identifier(table_name)
            count_res = db.execute(text(f"SELECT COUNT(*) FROM {quoted_table}"))
            count = count_res.scalar() or 0
        except Exception:
            count = 0
        tables.append({"name": table_name, "count": count})
    return {"tables": tables}


@app.get("/api/tdm/meta/domain")
def get_domain(db: Session = Depends(get_db)):
    """Returns the active domain name, inferred from generated active domain configuration."""
    return {"domain": get_active_domain_name()}


@app.get("/api/tdm/meta/schema-summary")
def get_schema_summary():
    """Returns active generated schema tables and columns without requiring generated rows."""
    _load_generated_modules()
    tables = []
    for table in Base.metadata.sorted_tables:
        tables.append({
            "name": table.name,
            "columns": [column.name for column in table.columns],
        })
    return {
        "domain": get_active_domain_name(),
        "slug": get_active_domain_slug(),
        "tables": tables,
    }


@app.get("/api/tdm/meta/domains")
def list_domains():
    """Lists all generated domains that have a domain.json."""
    generated_dir = _project_root / "generated"
    if not generated_dir.exists():
        return {"domains": [], "active": "general"}

    active = get_active_domain_slug()
    domains = []
    
    # List subdirectories of generated/
    for item in generated_dir.iterdir():
        if item.is_dir() and (item / "domain.json").exists():
            try:
                with open(item / "domain.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    domains.append({
                        "name": data.get("domain", item.name.replace("_", " ").title()),
                        "slug": item.name
                    })
            except Exception:
                domains.append({
                    "name": item.name.replace("_", " ").title(),
                    "slug": item.name
                })
                
    return {"domains": domains, "active": active}


@app.get("/api/tdm/meta/domain-aliases")
def get_domain_aliases():
    """Returns domain-specific table suggestions for UI prefill."""
    return {
        "suggested_tables": lead_agent.SUGGESED_TABLES,
        # Backward-compatible key for older UI code paths.
        "domain_aliases": lead_agent.SUGGESED_TABLES,
    }


@app.delete("/api/tdm/meta/domain/{slug}")
def delete_domain(slug: str):
    """Deletes a generated domain folder and its associated domain-specific database."""
    generated_dir = _project_root / "generated"
    domain_dir = generated_dir / slug
    if not domain_dir.exists() or not domain_dir.is_dir():
        raise HTTPException(status_code=404, detail="Domain folder not found")
    if slug == "general":
        raise HTTPException(status_code=400, detail="Cannot delete the general fallback domain")
    if not (domain_dir / "domain.json").exists():
        raise HTTPException(status_code=404, detail="Domain metadata not found")

    active_slug = get_active_domain_slug()
    new_active = None
    try:
        # If deleting the currently active domain, choose a fallback active domain.
        if active_slug == slug:
            engine.dispose()
            remaining = [item.name for item in generated_dir.iterdir()
                         if item.is_dir() and item.name != slug and (item / "domain.json").exists()]
            new_active = remaining[0] if remaining else "general"
            active_json_path = generated_dir / "active_domain.json"
            with open(active_json_path, "w", encoding="utf-8") as f:
                json.dump({"active_domain": new_active}, f, indent=2)

        shutil.rmtree(domain_dir)
        logger.info(f"Deleted domain folder: {domain_dir}")

        if active_slug == slug:
            _load_generated_modules()
        return {"success": True, "deleted": slug, "active": new_active or active_slug}
    except Exception as e:
        logger.error(f"Failed to delete domain {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tdm/meta/switch-domain")
def switch_domain(slug: str):
    """Switches the active domain to the given slug."""
    generated_dir = _project_root / "generated"
    domain_dir = generated_dir / slug
    if not domain_dir.exists():
        raise HTTPException(status_code=404, detail="Domain folder not found")

    active_json_path = generated_dir / "active_domain.json"
    try:
        with open(active_json_path, "w", encoding="utf-8") as f:
            json.dump({"active_domain": slug}, f, indent=2)
        logger.info(f"Switched active domain to {slug}")
        return {"success": True, "active_domain": slug}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write active_domain.json: {e}")


@app.get("/api/tdm/meta/table/{table_name}")
def get_table_data(table_name: str, limit: int = 500, db: Session = Depends(get_db)):
    """Fetches columns and row data for a requested table."""
    tables_res = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    valid_tables = [r[0] for r in tables_res.all()]
    if table_name not in valid_tables:
        raise HTTPException(status_code=404, detail="Invalid table name")

    # Query total rows in database for this table
    quoted_table = _quote_identifier(table_name)
    count_res = db.execute(text(f"SELECT COUNT(*) FROM {quoted_table}"))
    total_rows = count_res.scalar() or 0

    result = db.execute(text(f"SELECT * FROM {quoted_table} LIMIT :limit"), {"limit": limit})
    columns = list(result.keys())
    rows = [dict(row) for row in result.mappings().all()]
    return {"columns": columns, "rows": rows, "total": total_rows}


class SQLQuery(BaseModel):
    query: str

@app.post("/api/tdm/meta/query")
def execute_custom_query(sql: SQLQuery, db: Session = Depends(get_db)):
    """Executes raw SQL query from the frontend."""
    try:
        result = db.execute(text(sql.query))
        upper = sql.query.lstrip().upper()
        if upper.startswith("SELECT") or upper.startswith("PRAGMA"):
            columns = list(result.keys())
            rows = [dict(row) for row in result.mappings().all()]
            return {"columns": columns, "rows": rows}
        else:
            db.commit()
            return {"columns": ["Result"], "rows": [{"Result": f"OK. Rows affected: {result.rowcount}"}]}
    except Exception as e:
        return {"error": str(e), "columns": [], "rows": []}


# --- CRUD Endpoints ---

class RowData(BaseModel):
    data: dict

class RowIdentifier(BaseModel):
    where: dict  # column -> value pairs to identify the row


def _validate_table(table_name: str, db: Session) -> list[str]:
    """Validates table exists and returns list of valid tables."""
    tables_res = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    valid = [r[0] for r in tables_res.all()]
    if table_name not in valid:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return valid


@app.post("/api/tdm/meta/table/{table_name}/row")
def insert_row(table_name: str, body: RowData, db: Session = Depends(get_db)):
    """Insert a new row into a table."""
    _validate_table(table_name, db)
    quoted_table = _quote_identifier(table_name)
    cols = ", ".join([_quote_identifier(k) for k in body.data.keys()])
    placeholders = ", ".join([f":{k}" for k in body.data.keys()])
    query = f"INSERT INTO {quoted_table} ({cols}) VALUES ({placeholders})"
    try:
        db.execute(text(query), body.data)
        db.commit()
        return {"success": True, "message": "Row inserted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/tdm/meta/table/{table_name}/row")
def update_row(table_name: str, body: RowData, where: str = "", db: Session = Depends(get_db)):
    """Update a row. Pass where as query param like 'id=5'."""
    _validate_table(table_name, db)
    if not where:
        raise HTTPException(status_code=400, detail="'where' query param required (e.g. where=id=5)")
    quoted_table = _quote_identifier(table_name)
    set_clause = ", ".join([f"{_quote_identifier(k)} = :{k}" for k in body.data.keys()])
    # Parse where param: "col=val"
    w_parts = where.split("=", 1)
    if len(w_parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid where format. Use col=value")
    w_col, w_val = w_parts
    quoted_where_col = _quote_identifier(w_col)
    params = {**body.data, "_where_val": w_val}
    query = f"UPDATE {quoted_table} SET {set_clause} WHERE {quoted_where_col} = :_where_val"
    try:
        result = db.execute(text(query), params)
        db.commit()
        return {"success": True, "rows_affected": result.rowcount}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/tdm/meta/table/{table_name}/row")
def delete_row(table_name: str, where: str = "", db: Session = Depends(get_db)):
    """Delete a row. Pass where as query param like 'id=5'."""
    _validate_table(table_name, db)
    if not where:
        raise HTTPException(status_code=400, detail="'where' query param required")
    w_parts = where.split("=", 1)
    if len(w_parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid where format")
    w_col, w_val = w_parts
    quoted_table = _quote_identifier(table_name)
    quoted_where_col = _quote_identifier(w_col)
    query = f"DELETE FROM {quoted_table} WHERE {quoted_where_col} = :val"
    try:
        result = db.execute(text(query), {"val": w_val})
        db.commit()
        return {"success": True, "rows_affected": result.rowcount}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# --- Health Check ---

@app.get("/api/tdm/health")
def health_check():
    """Returns system health including LLM connectivity."""
    from app.config import get_llm_config
    llm_cfg = get_llm_config()
    has_key = bool(llm_cfg.get("api_key"))

    active_slug = get_active_domain_slug()
    active_dir = _project_root / "generated" / active_slug
    result = {
        "server": "running",
        "llm_provider": llm_cfg.get("provider"),
        "llm_model": llm_cfg.get("model"),
        "api_key_configured": has_key,
        "generated_files": {
            "models": (active_dir / "models.py").exists(),
            "schema_routes": (active_dir / "schema_routes.py").exists(),
        },
    }

    # Quick LLM connectivity test if key is present
    if has_key:
        try:
            from app.llm import get_llm_client
            client = get_llm_client()
            llm_health = client.health_check()
            result["llm_status"] = llm_health["status"]
        except Exception as e:
            result["llm_status"] = f"error: {e}"
    else:
        result["llm_status"] = "no_api_key"

    return result
