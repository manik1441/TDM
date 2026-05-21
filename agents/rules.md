# System Rules & Conventions

## Overview
These rules define the semantic standards, code conventions, and general system behavior for all agents within the Test Data Management (TDM) framework.

## 1. Code Conventions
- **Language**: Python 3.10+
- **Typing**: Use strict type hints for all function signatures (e.g., `def build_spec(data: dict) -> dict:`).
- **Frameworks**: 
  - FastAPI for API Routes.
  - SQLAlchemy 2.0 for Database Models.
  - Faker for Data Generation.
- **Naming Conventions**:
  - `snake_case` for variables, functions, and file names.
  - `PascalCase` for SQLAlchemy models and Pydantic schemas.
  - `UPPER_SNAKE_CASE` for global constants.

## 2. API Semantics
- **Endpoints**: Use RESTful semantic paths.
  - `GET /api/tdm/<entity>`
  - `POST /api/tdm/<entity>`
- **Responses**: Always return structured JSON.
  - Success: `{"success": true, "data": {...}}`
  - Error: `{"success": false, "error": "Reason"}`

## 3. Database Standardization
- Every generated table MUST have an `id` column as the Unique identifier and primary key if there is no primary mentioned in domain specification(`Integer, primary_key=True, index=True`).
- Foreign Keys must be strictly defined to ensure referential integrity.
- Use generic standard names for tables (e.g., `users`, `orders`, `products`) unless specified otherwise by the user domain.
