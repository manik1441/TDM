"""
Generator agent shim for TDM.

This module provides the legacy generator agent interface expected by the pipeline,
while delegating runtime synthetic data generation to `app.engine.data_generator`.
It also writes the two required generated files, but does not persist obsolete
`generator.py` files for data population.
"""

import json
import re
from pathlib import Path
from typing import Any

from app.llm import run_markdown_agent
from app.logger import get_logger

logger = get_logger(__name__)
_project_root = Path(__file__).parent.parent.parent


def _slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug or "general"


def _is_placeholder(content: str) -> bool:
    text = (content or "").strip()
    return text in {"...", "TODO", "TBD", "pass"}


def _strip_code_fence(content: str) -> str:
    """Extract inner content when a full response is wrapped in markdown code fences."""
    text = (content or "").strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return text


def _clean_generated_code(content: str) -> str:
    """Normalize common LLM formatting mistakes in generated Python code.

    Fixes:
    - Backslash line-continuations used instead of real newlines
    - Literal '\\n' sequences left un-decoded
    - Leading/trailing quote wrappers
    - Trailing backslash-comma artifacts
    """
    text = (content or "").strip()
    if not text:
        return text

    # Strip wrapping quotes (some models wrap the entire value in extra quotes)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    # Remove trailing ",\ artifacts
    if text.endswith('",\\'):
        text = text[:-3].strip()
    elif text.endswith(',\\'):
        text = text[:-2].strip()

    # If the text contains backslash-then-newline (continuation), the LLM likely
    # used `\` instead of `\n` inside a JSON string.  Replace `\<newline>` with
    # a plain newline so the Python is valid.
    text = re.sub(r'\\\n', '\n', text)

    # Replace literal two-char sequences \n / \t that were not JSON-decoded
    text = text.replace('\\n', '\n').replace('\\t', '\t')

    # Unescape remaining JSON escapes
    text = text.replace('\\"', '"').replace("\\\'" , "'")

    # Collapse any triple+ blank lines into double
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    return text.strip()


def _safe_json_loads(text: str) -> dict[str, Any]:
    """Best-effort JSON parse for slightly malformed LLM outputs."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty generator response")
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        loaded = json.loads(candidate)
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("Generator response was not valid JSON")


def _extract_from_raw_text(text: str) -> tuple[str, str]:
    """Fallback extractor when JSON is malformed but key blocks are present."""
    raw = text or ""
    models_match = re.search(r'"models_py"\s*:\s*"(?P<val>(?:\\.|[^"\\])*)"', raw, flags=re.S)
    routes_match = re.search(r'"schema_routes_py"\s*:\s*"(?P<val>(?:\\.|[^"\\])*)"', raw, flags=re.S)
    if models_match and routes_match:
        models_text = bytes(models_match.group("val"), "utf-8").decode("unicode_escape")
        routes_text = bytes(routes_match.group("val"), "utf-8").decode("unicode_escape")
        return models_text, routes_text

    models_text = _extract_jsonish_segment(raw, ["models_py", "models.py", "models"], ["schema_routes_py", "schema_routes.py"])
    routes_text = _extract_jsonish_segment(raw, ["schema_routes_py", "schema_routes.py"], [])
    return models_text, routes_text


def _extract_jsonish_segment(raw: str, keys: list[str], next_keys: list[str]) -> str:
    """Pull a value segment out of broken JSON where code quotes were not escaped."""
    lower = (raw or "").lower()
    key_positions = []
    for key in keys:
        for needle in (f'"{key.lower()}"', f"'{key.lower()}'", key.lower()):
            idx = lower.find(needle)
            if idx >= 0:
                key_positions.append((idx, needle))
    if not key_positions:
        return ""

    start, needle = min(key_positions, key=lambda item: item[0])
    colon = raw.find(":", start + len(needle))
    if colon < 0:
        return ""

    next_positions = []
    for key in next_keys:
        for next_needle in (f'"{key.lower()}"', f"'{key.lower()}'", key.lower()):
            idx = lower.find(next_needle, colon + 1)
            if idx >= 0:
                next_positions.append(idx)
    end = min(next_positions) if next_positions else len(raw)
    segment = raw[colon + 1:end].strip()
    if segment.endswith(","):
        segment = segment[:-1].strip()
    if len(segment) >= 2 and segment[0] in {"'", '"'}:
        segment = segment[1:]
    if len(segment) >= 1 and segment[-1] in {"'", '"'}:
        segment = segment[:-1]
    return (
        segment
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\'", "'")
        .strip()
    )


def _extract_from_markdown_sections(text: str) -> tuple[str, str]:
    """Extract code when the model ignores JSON and returns labeled code fences."""
    raw = text or ""
    models_text = ""
    routes_text = ""
    fenced_blocks = []

    for match in re.finditer(r"```(?:python|py)?\s*\n(?P<code>.*?)```", raw, flags=re.S | re.I):
        code = match.group("code").strip()
        prefix = raw[max(0, match.start() - 160):match.start()].lower()
        fenced_blocks.append(code)
        if ("models_py" in prefix or "models.py" in prefix or "models" in prefix) and not models_text:
            models_text = code
        elif ("schema_routes_py" in prefix or "schema_routes.py" in prefix or "routes" in prefix) and not routes_text:
            routes_text = code

    if (not models_text or not routes_text) and len(fenced_blocks) >= 2:
        models_text = models_text or fenced_blocks[0]
        routes_text = routes_text or fenced_blocks[1]

    return models_text, routes_text


def _extract_generated_files(payload: dict[str, Any]) -> tuple[str, str]:
    """
    Extract models/routes content from common generator response shapes.

    Accepts:
    - top-level keys: models_py, schema_routes_py
    - filename keys: models.py, schema_routes.py
    - nested object under `files`
    - common alternates: models, routes, schema_routes, schema_routes_code
    """
    source = payload or {}
    files_obj = source.get("files")
    if isinstance(files_obj, dict):
        merged = dict(source)
        merged.update(files_obj)
        source = merged

    models_text = (
        source.get("models_py")
        or source.get("models.py")
        or source.get("models")
        or source.get("models_code")
    )
    routes_text = (
        source.get("schema_routes_py")
        or source.get("schema_routes.py")
        or source.get("schema_routes")
        or source.get("routes")
        or source.get("routes_py")
        or source.get("schema_routes_code")
    )
    return str(models_text or ""), str(routes_text or "")


def _extract_entities_from_prompt(prompt: str) -> list[str]:
    raw = prompt or ""
    m = re.search(r"\*\*Core Entities\*\*:\s*(.+)", raw, flags=re.I)
    if not m:
        m = re.search(r"-\s*Core Entities/Tables:\s*(.+)", raw, flags=re.I)
    raw_entities = (m.group(1) if m else "Records").strip()
    parts = [p.strip() for p in re.split(r"[,/|;\n]+", raw_entities) if p and p.strip()]
    return parts or ["Records"]


def _normalize_entity_name(name: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    if lowered.endswith("s"):
        return lowered[:-1]
    return lowered


def _extract_generated_tables(models_text: str) -> set[str]:
    tables = set()
    for match in re.finditer(r'__tablename__\s*=\s*["\']([^"\']+)["\']', models_text or ""):
        tables.add(_normalize_entity_name(match.group(1)))
    return tables


def _validate_entities_covered(prompt: str, models_text: str) -> None:
    expected_entities = _extract_entities_from_prompt(prompt)
    expected = {_normalize_entity_name(e) for e in expected_entities if e and e.strip()}
    actual = _extract_generated_tables(models_text)
    missing = sorted([e for e in expected if e and e not in actual])
    if missing:
        raise ValueError(
            "Generated models missing entities from Core Entities / Tables: "
            + ", ".join(missing)
        )


def _entity_to_names(entity: str) -> tuple[str, str]:
    table_name = re.sub(r"[^a-z0-9]+", "_", (entity or "").strip().lower()).strip("_")
    table_name = table_name or "records"
    class_base = re.sub(r"[^A-Za-z0-9]+", " ", table_name).title().replace(" ", "")
    if class_base.endswith("s") and len(class_base) > 1:
        class_base = class_base[:-1]
    if not class_base or class_base[0].isdigit():
        class_base = f"Generated{class_base or 'Record'}"
    return class_base, table_name


def generate_local_code(requirements_spec: dict[str, Any]) -> dict[str, Any]:
    """Generate schema files locally from Core Entities / Tables without an LLM."""
    entities_raw = str(requirements_spec.get("entities") or "").strip()
    entities = [p.strip() for p in re.split(r"[,/|;\n]+", entities_raw) if p and p.strip()]
    if not entities:
        return {"success": False, "error": "Core Entities / Tables is required for offline generation"}

    names = [_entity_to_names(entity) for entity in entities]
    model_blocks = []
    for class_name, table_name in names:
        model_blocks.append(f'''class {class_name}(Base):
    __tablename__ = "{table_name}"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    status = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
''')

    models_py = (
        "from sqlalchemy import Column, String, Integer, Text\n"
        "from app.db import Base\n\n\n"
        + "\n".join(model_blocks)
    )

    imports = ", ".join(class_name for class_name, _ in names)
    route_blocks = []
    for class_name, table_name in names:
        route_blocks.append(f'''@router.get("/{table_name}")
def list_{table_name}(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = db.query({class_name}).limit(limit).all()
    return [{{col.name: getattr(row, col.name) for col in {class_name}.__table__.columns}} for row in rows]


@router.post("/{table_name}")
def create_{table_name}(data: dict = Body(...), db: Session = Depends(get_db)):
    allowed = {{col.name for col in {class_name}.__table__.columns if col.name != "id"}}
    item = {class_name}(**{{key: value for key, value in data.items() if key in allowed}})
    db.add(item)
    db.commit()
    db.refresh(item)
    return {{col.name: getattr(item, col.name) for col in {class_name}.__table__.columns}}
''')

    schema_routes_py = (
        "from fastapi import APIRouter, Depends, Query, Body\n"
        "from sqlalchemy.orm import Session\n"
        "from app.db import get_db\n"
        f"from models import {imports}\n\n\n"
        "router = APIRouter(prefix=\"/api/tdm\")\n\n\n"
        + "\n".join(route_blocks)
    )

    prompt = f"**Core Entities**: {', '.join(entities)}"
    _validate_entities_covered(prompt, models_py)
    return {
        "success": True,
        "files": {
            "models_py": models_py,
            "schema_routes_py": schema_routes_py,
        },
    }


def generate_code(prompt: str, generation_feedback: str | None = None) -> dict[str, Any]:
    """Generate model and route code from the markdown generator agent."""
    last_error = "Unknown generator failure"
    feedback = generation_feedback
    for attempt in range(2):
        user_content = prompt
        if feedback:
            user_content += (
                f"\n\nPrevious generation feedback: {feedback}"
                "\nReturn strict JSON only with non-empty string keys `models_py` and `schema_routes_py`."
                "\nDo not return placeholders like `...`, `TODO`, `TBD`, or `pass`."
                "\nBoth values must contain complete, executable Python code."
                "\nDo not use markdown fences."
            )

        try:
            result_text = run_markdown_agent("generator", user_content, json_mode=True, temperature=0.2, max_tokens=6000)
            if isinstance(result_text, dict):
                generated = result_text
                models_text, routes_text = _extract_generated_files(generated)
            else:
                try:
                    generated = _safe_json_loads(result_text)
                    if not isinstance(generated, dict):
                        raise ValueError("Generator response was not a JSON object")
                    models_text, routes_text = _extract_generated_files(generated)
                except Exception:
                    models_text, routes_text = _extract_from_raw_text(result_text)
                    if not models_text.strip() or not routes_text.strip():
                        models_text, routes_text = _extract_from_markdown_sections(result_text)

            models_text = _clean_generated_code(_strip_code_fence(models_text))
            routes_text = _clean_generated_code(_strip_code_fence(routes_text))

            if not models_text.strip() or not routes_text.strip():
                raise ValueError("Generator response did not include extractable models.py and schema_routes.py code")
            if _is_placeholder(models_text) or _is_placeholder(routes_text):
                raise ValueError("Generator returned placeholder content instead of code")
            _validate_entities_covered(prompt, models_text)

            return {
                "success": True,
                "files": {
                    "models_py": models_text,
                    "schema_routes_py": routes_text,
                },
            }
        except Exception as exc:
            last_error = str(exc)
            feedback = last_error
            # Keep retry noise out of normal logs; only final failure is logged as error.
            logger.info(f"Generator retry {attempt + 1}/2 due to invalid output.")

    logger.error(f"Generator agent failed: {last_error}")
    return {"success": False, "error": last_error}


def write_generated_files(generated_files: dict[str, str], domain: str) -> dict[str, Any]:
    """Write generated model and schema route files for the selected domain."""
    slug = _slugify(domain or "general")
    generated_root = _project_root / "generated"
    domain_dir = generated_root / slug
    domain_dir.mkdir(parents=True, exist_ok=True)

    written = []
    try:
        models_py = generated_files.get("models_py")
        if models_py is not None and str(models_py).strip() and not _is_placeholder(str(models_py)):
            (domain_dir / "models.py").write_text(models_py, encoding="utf-8")
            written.append("models.py")
        else:
            raise ValueError("Refusing to write blank/placeholder models.py")

        schema_routes_py = generated_files.get("schema_routes_py")
        if schema_routes_py is not None and str(schema_routes_py).strip() and not _is_placeholder(str(schema_routes_py)):
            (domain_dir / "schema_routes.py").write_text(schema_routes_py, encoding="utf-8")
            written.append("schema_routes.py")
        else:
            raise ValueError("Refusing to write blank/placeholder schema_routes.py")

        domain_metadata = {
            "domain": domain or slug.replace("_", " ").title(),
            "slug": slug,
        }
        (domain_dir / "domain.json").write_text(json.dumps(domain_metadata, indent=2), encoding="utf-8")
        written.append("domain.json")

        active_json_path = generated_root / "active_domain.json"
        active_json_path.write_text(json.dumps({"active_domain": slug}, indent=2), encoding="utf-8")
        written.append("active_domain.json")

        # Ensure no obsolete `generator.py` remains in the generated domain folder.
        obsolete_path = domain_dir / "generator.py"
        if obsolete_path.exists():
            obsolete_path.unlink()
            logger.info(f"Removed obsolete generated file: {obsolete_path}")

        return {"success": True, "written": written}
    except Exception as exc:
        logger.error(f"Failed to write generated files: {exc}")
        return {"success": False, "error": str(exc)}
