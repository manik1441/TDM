"""Pipeline coordinator for Lead -> Prompt Builder -> Generator."""
"""
 Orchestrates the end-to-end flow: starts sessions, runs lead intake, 
 builds prompt-builder input, calls generator with retries, writes generated files, 
 tracks stage status, and emits progress updates. 
 It also manages data-generation sessions, table-wise execution state, active domain loading,
 and final success or failure lifecycle reporting robustly.
"""
import importlib
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

from app.engine import models_generator as generator_agent
from app.engine import lead as lead_agent
from app.config import get_llm_config
from app.llm import run_markdown_agent
from app.logger import get_logger

logger = get_logger(__name__)

_project_root = Path(__file__).parent.parent.parent
_sessions: dict[str, dict] = {}
_data_sessions: dict[str, dict] = {}

MAX_GENERATION_ATTEMPTS = 2


def get_session(session_id: str) -> dict | None:
    """Return pipeline session state."""
    return _sessions.get(session_id)


def get_all_sessions() -> dict:
    """Return all pipeline sessions."""
    return dict(_sessions)


def start_pipeline(user_input: str, on_status: Callable | None = None) -> dict:
    """Start the pipeline from a raw user prompt."""
    session_id = str(uuid.uuid4())[:8]
    _sessions[session_id] = {
        "session_id": session_id,
        "stage": "intake",
        "status": "running",
        "user_input": user_input,
        "stages": {},
        "created_at": time.time(),
    }

    _emit(session_id, "intake", "running", "Lead Agent is analyzing your request...", on_status)
    validation = lead_agent.validate_input(user_input)
    _sessions[session_id]["stages"]["intake"] = validation

    if not validation.get("is_valid"):
        _sessions[session_id]["status"] = "rejected"
        _sessions[session_id]["stage"] = "intake"
        _emit(session_id, "intake", "rejected", validation.get("message", "Request rejected"), on_status)
        return {
            "session_id": session_id,
            "stage": "intake",
            "status": "rejected",
            "result": validation,
            "needs_followup": False,
        }

    if validation.get("needs_followup"):
        _sessions[session_id]["status"] = "awaiting_input"
        _sessions[session_id]["stage"] = "intake_followup"
        questions = lead_agent.get_structured_questions(validation.get("extracted"))
        _emit(session_id, "intake", "awaiting_input", "Need more details - please fill the form", on_status)
        return {
            "session_id": session_id,
            "stage": "intake_followup",
            "status": "awaiting_input",
            "result": validation,
            "questions": questions,
            "needs_followup": True,
        }

    _emit(session_id, "intake", "complete", "Requirements understood", on_status)
    return {
        "session_id": session_id,
        "stage": "intake_complete",
        "status": "ready",
        "result": validation,
        "needs_followup": False,
    }


def continue_pipeline(
    session_id: str,
    structured_answers: dict,
    on_status: Callable | None = None,
) -> dict:
    """Run: Build Spec -> Prompt Builder -> Generator -> Write Files."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    user_input = session["user_input"]
    extracted = session.get("stages", {}).get("intake", {}).get("extracted")

    _emit(session_id, "spec_building", "running", "Building requirements specification...", on_status)
    spec = lead_agent.build_requirements_spec(user_input, structured_answers, extracted)
    session["stages"]["spec"] = spec
    session["stage"] = "spec_building"
    _emit(session_id, "spec_building", "complete", "Requirements spec ready", on_status)

    if get_llm_config().get("offline_mode"):
        _emit(session_id, "code_generation", "running", "Offline mode generating schema from Core Entities / Tables...", on_status)
        gen_result = generator_agent.generate_local_code(spec)
        session["stages"]["code_gen_offline"] = {
            "success": gen_result["success"],
            "error": gen_result.get("error"),
        }
        session["stage"] = "code_generation"
        if not gen_result["success"]:
            session["status"] = "failed"
            _emit(session_id, "code_generation", "failed", gen_result["error"], on_status)
            return {"session_id": session_id, "status": "failed", "error": gen_result["error"]}

        _emit(session_id, "code_generation", "complete", "Offline schema generated", on_status)
        _emit(session_id, "writing_files", "running", "Writing generated files...", on_status)
        write_result = generator_agent.write_generated_files(gen_result["files"], spec.get("domain", "General"))
        session["stages"]["write"] = write_result
        session["stage"] = "writing_files"
        if write_result["success"]:
            session["status"] = "complete"
            session["stage"] = "complete"
            _emit(session_id, "pipeline", "complete", f"Pipeline complete! Files written: {', '.join(write_result['written'])}", on_status)
            return {
                "session_id": session_id,
                "status": "complete",
                "written_files": write_result["written"],
                "scale_factor": spec.get("scale_factor", 0.1),
                "mode": "offline",
            }

        session["status"] = "failed"
        _emit(session_id, "writing_files", "failed", f"Write failed: {write_result['error']}", on_status)
        return {"session_id": session_id, "status": "failed", "error": write_result["error"]}

    _emit(session_id, "prompt_building", "running", "Prompt Builder is crafting the optimal prompt...", on_status)
    prompt = _build_generation_prompt(spec)
    session["stages"]["prompt"] = {"prompt": prompt[:500] + "..."}
    session["stage"] = "prompt_building"
    _emit(session_id, "prompt_building", "complete", "Prompt crafted", on_status)

    attempt = 0
    generated_files = None
    generation_feedback = None

    while attempt < MAX_GENERATION_ATTEMPTS:
        _emit(session_id, "code_generation", "running", f"Generator Agent producing code (attempt {attempt + 1})...", on_status)
        gen_result = generator_agent.generate_code(prompt, generation_feedback)
        session["stages"][f"code_gen_{attempt}"] = {
            "success": gen_result["success"],
            "error": gen_result.get("error"),
        }
        session["stage"] = "code_generation"

        if gen_result["success"]:
            generated_files = gen_result["files"]
            _emit(session_id, "code_generation", "complete", "Code generated", on_status)
            break

        _emit(session_id, "code_generation", "failed", f"Generation failed: {gen_result['error']}", on_status)
        if attempt < MAX_GENERATION_ATTEMPTS - 1:
            generation_feedback = gen_result["error"]
            attempt += 1
            continue

        session["status"] = "failed"
        return {"session_id": session_id, "status": "failed", "error": gen_result["error"]}

    if not generated_files:
        session["status"] = "failed"
        _emit(session_id, "pipeline", "failed", "Code generation failed after max attempts", on_status)
        return {"session_id": session_id, "status": "failed", "error": "Max generation attempts exceeded"}

    _emit(session_id, "writing_files", "running", "Writing generated files...", on_status)
    write_result = generator_agent.write_generated_files(generated_files, spec.get("domain", "General"))
    session["stages"]["write"] = write_result
    session["stage"] = "writing_files"

    if write_result["success"]:
        session["status"] = "complete"
        session["stage"] = "complete"
        _emit(session_id, "pipeline", "complete", f"Pipeline complete! Files written: {', '.join(write_result['written'])}", on_status)
        return {
            "session_id": session_id,
            "status": "complete",
            "written_files": write_result["written"],
            "scale_factor": spec.get("scale_factor", 0.1),
        }

    session["status"] = "failed"
    _emit(session_id, "writing_files", "failed", f"Write failed: {write_result['error']}", on_status)
    return {"session_id": session_id, "status": "failed", "error": write_result["error"]}


def get_data_session(session_id: str) -> dict | None:
    """Return a data generation session."""
    return _data_sessions.get(session_id)


def run_data_generation(
    scale_factor: float = 0.1,
    on_table_status: Callable | None = None,
) -> dict:
    """Run generated data scripts with table-wise progress tracking."""
    session_id = str(uuid.uuid4())[:8]
    generated_dir = _project_root / "generated"
    active_slug = "general"
    active_json_path = generated_dir / "active_domain.json"
    if active_json_path.exists():
        try:
            import json
            with open(active_json_path, "r", encoding="utf-8") as f:
                active_slug = json.load(f).get("active_domain", "general")
        except Exception:
            pass

    active_dir = generated_dir / active_slug
    gen_str = str(active_dir)
    if gen_str not in sys.path:
        sys.path.insert(0, gen_str)
    elif sys.path[0] != gen_str:
        sys.path.remove(gen_str)
        sys.path.insert(0, gen_str)

    tables = _discover_tables()
    _data_sessions[session_id] = {
        "session_id": session_id,
        "status": "running",
        "scale_factor": scale_factor,
        "tables": {t: {"status": "queued", "message": "In queue"} for t in tables},
        "started_at": time.time(),
    }

    def emit_table(table: str, status: str, message: str):
        _data_sessions[session_id]["tables"][table] = {
            "status": status,
            "message": message,
            "updated_at": time.time(),
        }
        if on_table_status:
            on_table_status(session_id, table, status, message)

    try:
        if not (active_dir / "models.py").exists():
            _data_sessions[session_id]["status"] = "failed"
            _data_sessions[session_id]["error"] = f"models.py not found under '{active_slug}' - run the pipeline first"
            return _data_sessions[session_id]

        from app.db import Base, SessionLocal, engine
        from app.engine import data_generator

        db = SessionLocal()
        try:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)

            for table in tables:
                emit_table(table, "in_progress", "Generating data...")

            data_generator.generate_universal_data(db, scale_factor=scale_factor)

            for table in tables:
                emit_table(table, "complete", "Complete")
        finally:
            db.close()

        _data_sessions[session_id]["status"] = "complete"
        _data_sessions[session_id]["finished_at"] = time.time()
    except Exception as e:
        _data_sessions[session_id]["status"] = "failed"
        _data_sessions[session_id]["error"] = str(e)
        logger.error(f"Data generation session [{session_id}] failed: {e}")

    return _data_sessions[session_id]


def _build_generation_prompt(requirements_spec: dict) -> str:
    """Build the Generator prompt from markdown instructions and requirements."""
    user_content = f"""Here is the structured requirements specification:

**Original User Request**: {requirements_spec.get('original_prompt', 'N/A')}
**Domain**: {requirements_spec.get('domain', 'General')}
**Core Entities**: {requirements_spec.get('entities', 'Not specified')}
**Data Audience**: {requirements_spec.get('audience', 'QA / Test Automation')}
**Data Volume**: {requirements_spec.get('volume', 'Medium')} (scale_factor={requirements_spec.get('scale_factor', 0.1)})
**Synthetic Ratio**: {requirements_spec.get('synthetic_ratio', '100% Synthetic')}
**Special Constraints**: {requirements_spec.get('constraints', 'None specified')}
**Key Relationships**: {requirements_spec.get('relationships', 'None specified')}

Generate the optimal prompt for code generation."""

    base_prompt = run_markdown_agent("prompt_builder", user_content, temperature=0.2).strip()
    domain = requirements_spec.get("domain", "General")
    entities = requirements_spec.get("entities", "Not specified")
    hard_requirements = (
        "\n\n---\n"
        "MANDATORY REQUIREMENTS (DO NOT IGNORE):\n"
        f"- Domain: {domain}\n"
        f"- Core Entities/Tables: {entities}\n"
        "- models.py MUST include table models aligned to the listed entities.\n"
        "- schema_routes.py MUST expose routes for those entities.\n"
    )
    return base_prompt + hard_requirements


def _discover_tables() -> list[str]:
    """Get table names from SQLite or generated models."""
    try:
        from app.db import engine
        from sqlalchemy import inspect as sa_inspect

        tables = sa_inspect(engine).get_table_names()
        if tables:
            return tables
    except Exception:
        pass

    try:
        generated_dir = _project_root / "generated"
        active_slug = "general"
        active_json_path = generated_dir / "active_domain.json"
        if active_json_path.exists():
            try:
                import json
                with open(active_json_path, "r", encoding="utf-8") as f:
                    active_slug = json.load(f).get("active_domain", "general")
            except Exception:
                pass

        active_dir = generated_dir / active_slug
        gen_str = str(active_dir)
        if gen_str not in sys.path:
            sys.path.insert(0, gen_str)
        elif sys.path[0] != gen_str:
            sys.path.remove(gen_str)
            sys.path.insert(0, gen_str)

        if "models" in sys.modules:
            importlib.reload(sys.modules["models"])
        else:
            importlib.import_module("models")
        from app.db import Base

        return list(Base.metadata.tables.keys())
    except Exception:
        return ["unknown"]


def _emit(session_id: str, stage: str, status: str, message: str, callback: Callable | None):
    """Record and optionally emit a status update."""
    logger.info(f"[{session_id}] {stage}: {status} - {message}")
    if session_id in _sessions:
        _sessions[session_id].setdefault("timeline", []).append({
            "stage": stage,
            "status": status,
            "message": message,
            "timestamp": time.time(),
        })
    if callback:
        try:
            callback(session_id, stage, status, message)
        except Exception as e:
            logger.warning(f"Status callback error: {e}")

