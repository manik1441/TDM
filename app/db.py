import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_db_config

Base = declarative_base()


def get_dynamic_database_url() -> str:
    """Computes a dynamic database URL segregated by the active domain slug."""
    project_root = Path(__file__).parent.parent
    active_json_path = project_root / "generated" / "active_domain.json"
    slug = "general"
    if active_json_path.exists():
        try:
            with open(active_json_path, "r", encoding="utf-8") as f:
                slug = json.load(f).get("active_domain", "general")
        except Exception:
            pass

    db_config = get_db_config()
    base_url = db_config["url"]
    if base_url.startswith("sqlite:///"):
        domain_dir = project_root / "generated" / slug
        domain_dir.mkdir(parents=True, exist_ok=True)
        db_path = domain_dir / "test_data.db"
        return f"sqlite:///{db_path.resolve().as_posix()}"
    return base_url


class DynamicEngineProxy:
    """A proxy wrapper that routes all database connections to the active domain's engine."""
    def __init__(self):
        self._current_slug = None
        self._cached_engine = None

    def _get_active_slug(self) -> str:
        project_root = Path(__file__).parent.parent
        active_json_path = project_root / "generated" / "active_domain.json"
        slug = "general"
        if active_json_path.exists():
            try:
                with open(active_json_path, "r", encoding="utf-8") as f:
                    slug = json.load(f).get("active_domain", "general")
            except Exception:
                pass
        return slug

    def _create_engine(self, slug: str):
        db_url = get_dynamic_database_url()
        engine_obj = create_engine(db_url, connect_args={"check_same_thread": False})
        self._current_slug = slug
        self._cached_engine = engine_obj
        return engine_obj

    @property
    def _engine(self):
        slug = self._get_active_slug()
        if self._cached_engine is None or slug != self._current_slug:
            self.dispose()
            return self._create_engine(slug)
        return self._cached_engine

    def dispose(self):
        if self._cached_engine is not None:
            try:
                self._cached_engine.dispose()
            except Exception:
                pass
            self._cached_engine = None
            self._current_slug = None

    def __getattr__(self, name):
        return getattr(self._engine, name)


engine = DynamicEngineProxy()


class DynamicSessionLocalProxy:
    """A proxy wrapper that yields a new session factory for the active domain's engine."""
    def __call__(self, *args, **kwargs):
        db_engine = engine._engine
        return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)(*args, **kwargs)


SessionLocal = DynamicSessionLocalProxy()


def get_db():
    """FastAPI dependency that yields a segregated database session."""
    db_engine = engine._engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
