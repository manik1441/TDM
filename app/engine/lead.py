"""
Lead Agent — Data-domain gatekeeper and intake specialist.

Responsibilities:
- Validates that user input is data-related (rejects off-topic requests)
- Asks structured follow-up questions with dropdown options
- Produces a clean, structured requirements spec for the Prompt Builder
- Provides LLM-driven domain → table suggestions (cached)
"""

"""
Validates user intent, collects structured inputs, infers and normalizes domain, 
suggests core tables via LLM, and builds a clean requirements specification. 
It prepares authoritative fields like entities, volume, constraints, 
and relationships so downstream generation receives consistent, 
backend-safe inputs from form answers and extracted prompt context, 
with sensible defaults and fallbacks.
"""

import json
import re
import threading
from copy import deepcopy
from typing import Optional

from pydantic import BaseModel, Field

from app.config import get_llm_config
from app.llm import run_markdown_agent
from app.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOMAIN_OPTIONS = [
    "Healthcare",
    "E-Commerce",
    "Banking / Finance",
    "Education",
    "Logistics / Supply Chain",
    "Insurance",
    "Real Estate",
    "Hospitality",
    "Telecommunications",
    "Other",
]

DOMAIN_ALIASES = {
    "Healthcare": [
        "health", "hospital", "clinic", "doctor", "patient", "medical",
        "pharma", "pharmacy", "appointment", "prescription",
    ],
    "E-Commerce": [
        "e-commerce", "ecommerce", "commerce", "retail", "shop", "store",
        "order", "cart", "product", "customer", "payment",
    ],
    "Banking / Finance": [
        "bank", "banking", "finance", "financial", "loan", "account",
        "transaction", "credit", "debit", "mortgage",
    ],
    "Education": [
        "education", "school", "college", "university", "student",
        "teacher", "course", "class", "exam",
    ],
    "Logistics / Supply Chain": [
        "logistics", "shipment", "shipping", "supply", "warehouse",
        "inventory", "delivery", "fleet", "carrier",
    ],
    "Insurance": [
        "insurance", "policy", "claim", "premium", "coverage",
        "underwriting",
    ],
    "Real Estate": [
        "real estate", "property", "tenant", "lease", "rental",
        "broker", "realtor",
    ],
    "Hospitality": [
        "hospitality", "hotel", "reservation", "guest", "room", "restaurant",
    ],
    "Telecommunications": [
        "telecom", "telecommunication", "network", "subscriber",
        "plan", "call", "billing",
    ],
}

# Structured questions the Lead Agent can ask the user
STRUCTURED_QUESTIONS = {
    "questions": [
        {
            "id": "domain",
            "label": "Business Domain",
            "type": "dropdown",
            "options": DOMAIN_OPTIONS,
            "allow_custom": True,
            "custom_id": "domain_custom",
            "custom_label": "Other Domain",
            "custom_placeholder": "e.g. Airline, Legal, Automotive",
            "required": True,
        },
        {
            "id": "entities",
            "label": "Core Entities / Tables",
            "type": "text",
            "placeholder": "e.g. Doctors, Patients, Appointments, Prescriptions",
            "required": True,
        },
        {
            "id": "audience",
            "label": "Data Audience / Purpose",
            "type": "dropdown",
            "options": [
                "QA / Test Automation",
                "Performance Testing",
                "Analytics / BI",
                "Demo / Sales",
                "Development / Prototyping",
            ],
            "required": True,
        },
        {
            "id": "volume",
            "label": "Data Volume",
            "type": "dropdown",
            "options": [
                "Small (100s of rows)",
                "Medium (1K–10K rows)",
                "Large (10K–100K rows)",
                "Massive (100K+ rows)",
            ],
            "required": True,
        },
        {
            "id": "synthetic_ratio",
            "label": "Synthetic Data Ratio",
            "type": "dropdown",
            "options": [
                "100% Synthetic",
                "80% Synthetic / 20% Seeded",
                "50/50 Mix",
            ],
            "required": True,
        },
        {
            "id": "constraints",
            "label": "Special Constraints / Rules",
            "type": "textarea",
            "placeholder": "e.g. 10% cancelled orders, all doctors must have at least 1 patient, 30% null emails",
            "required": False,
        },
        {
            "id": "relationships",
            "label": "Key Relationships",
            "type": "textarea",
            "placeholder": "e.g. Each order belongs to a customer, each patient has one primary doctor",
            "required": False,
        },
    ]
}

# Volume mapping for downstream agents
VOLUME_MAP = {
    "Small (100s of rows)": 0.01,
    "Medium (1K–10K rows)": 0.1,
    "Large (10K–100K rows)": 0.5,
    "Massive (100K+ rows)": 1.0,
}


# ---------------------------------------------------------------------------
# Pydantic models for LLM response validation
# ---------------------------------------------------------------------------

class ExtractedRequirements(BaseModel):
    """Structured requirements extracted (or inferred) by the Lead Agent."""
    domain: str = ""
    entities: str = ""
    audience: str = "QA / Test Automation"
    volume: str = "Small (100s of rows)"
    synthetic_ratio: str = "100% Synthetic"
    constraints: str = ""
    relationships: str = ""


class LeadAgentResponse(BaseModel):
    """Validated shape of the Lead Agent's JSON response."""
    is_valid: bool
    message: str = ""
    needs_followup: bool = True
    extracted: Optional[ExtractedRequirements] = None


# ---------------------------------------------------------------------------
# LLM-driven domain → table suggestions (cached)
# ---------------------------------------------------------------------------

# Static fallback used when the LLM is unavailable or offline
_DEFAULT_TABLE_SUGGESTIONS: dict[str, list[str]] = {
    "Healthcare": ["Doctors", "Patients", "Appointments", "Prescriptions", "Departments"],
    "E-Commerce": ["Customers", "Products", "Orders", "Order_Items", "Categories"],
    "Banking / Finance": ["Users", "Accounts", "Transactions", "Loans", "Branches"],
    "Education": ["Students", "Teachers", "Courses", "Enrollments", "Exams"],
    "Logistics / Supply Chain": ["Warehouses", "Shipments", "Carriers", "Inventory", "Routes"],
    "Insurance": ["Policies", "Claims", "Customers", "Agents", "Premiums"],
    "Real Estate": ["Properties", "Tenants", "Leases", "Agents", "Payments"],
    "Hospitality": ["Hotels", "Rooms", "Guests", "Reservations", "Services"],
    "Telecommunications": ["Subscribers", "Plans", "Calls", "Billing", "Towers"],
}

_SUGGESTION_PROMPT = """You are a database domain expert. For each of the following business domains, suggest 5-7 core database tables/entities that would be typical for a real-world application in that domain. Use PascalCase or snake_case names that are appropriate for database table naming.

Domains: Healthcare, E-Commerce, Banking / Finance, Education, Logistics / Supply Chain, Insurance, Real Estate, Hospitality, Telecommunications

Respond ONLY with valid JSON — a single object mapping each domain name (exactly as listed) to an array of table name strings. No markdown, no explanation."""

_cached_suggestions: dict[str, list[str]] | None = None
_suggestions_lock = threading.Lock()


def get_domain_table_suggestions() -> dict[str, list[str]]:
    """
    Returns domain → suggested tables mapping.
    Calls the LLM on first request and caches the result.
    Falls back to static defaults if the LLM is unavailable.
    """
    global _cached_suggestions

    if _cached_suggestions is not None:
        return _cached_suggestions

    with _suggestions_lock:
        # Double-check after acquiring lock (another thread may have populated it)
        if _cached_suggestions is not None:
            return _cached_suggestions

        try:
            if get_llm_config().get("offline_mode"):
                logger.info("Offline mode — using default table suggestions")
                _cached_suggestions = dict(_DEFAULT_TABLE_SUGGESTIONS)
                return _cached_suggestions

            response = run_markdown_agent(
                "lead",
                "SUGGEST_DOMAIN_TABLES",
                json_mode=True,
                temperature=0.3,
                max_tokens=2048,
            )
            result = json.loads(response)

            # Validate shape: must be dict of string → list[str]
            if isinstance(result, dict) and all(
                isinstance(k, str) and isinstance(v, list) and all(isinstance(i, str) for i in v)
                for k, v in result.items()
            ):
                _cached_suggestions = result
                logger.info(f"LLM domain table suggestions cached for {len(result)} domains")
                return _cached_suggestions
            else:
                logger.warning("LLM returned unexpected shape for table suggestions, using defaults")

        except Exception as e:
            logger.warning(f"Failed to get LLM domain suggestions, using defaults: {e}")

        _cached_suggestions = dict(_DEFAULT_TABLE_SUGGESTIONS)
        return _cached_suggestions


def invalidate_suggestion_cache() -> None:
    """Clear the cached LLM suggestions so the next call re-fetches."""
    global _cached_suggestions
    with _suggestions_lock:
        _cached_suggestions = None
    logger.info("Domain table suggestion cache invalidated")


# ---------------------------------------------------------------------------
# Core Lead Agent functions
# ---------------------------------------------------------------------------

def validate_input(user_input: str) -> dict:
    """
    Uses the LLM to determine if the input is data-related
    and extracts any initial requirements.

    Returns:
        {
            "is_valid": bool,
            "message": str,           # Response message to user
            "needs_followup": bool,   # Whether structured questions should be shown
            "extracted": dict | None  # Any requirements extracted from the initial prompt
        }
    """
    logger.info(f"Lead Agent — validating input: {user_input[:100]}...")

    if get_llm_config().get("offline_mode"):
        return {
            "is_valid": True,
            "message": "Offline mode: fill the form to generate a local schema.",
            "needs_followup": True,
            "extracted": None,
        }

    response = run_markdown_agent("lead", user_input, json_mode=True)

    try:
        raw_result = json.loads(response)

        # Validate and normalize through Pydantic
        validated = LeadAgentResponse.model_validate(raw_result)
        result = validated.model_dump()

        # Convert extracted from Pydantic model to plain dict for downstream compat
        if result.get("extracted") is not None:
            result["extracted"] = dict(result["extracted"])

        # Safety net: if the LLM forgot needs_followup, default to True
        if "needs_followup" not in raw_result and result.get("is_valid"):
            result["needs_followup"] = True
            logger.warning("Lead Agent — LLM omitted needs_followup, defaulting to True")

        logger.info(
            f"Lead Agent — validation result: valid={result.get('is_valid')}, "
            f"followup={result.get('needs_followup')}"
        )
        return result

    except json.JSONDecodeError:
        logger.error(f"Lead Agent — failed to parse LLM response: {response[:200]}")
        return {
            "is_valid": True,
            "message": "I understand your request. Let me gather some more details.",
            "needs_followup": True,
            "extracted": None,
        }
    except Exception as e:
        logger.error(f"Lead Agent — validation error: {e}")
        return {
            "is_valid": True,
            "message": "I understand your request. Let me gather some more details.",
            "needs_followup": True,
            "extracted": None,
        }


def _normalize_domain(raw_domain: str | None) -> tuple[str | None, str]:
    """Map an extracted domain to a known option, or Other with custom text."""
    if not raw_domain:
        return None, ""

    domain = str(raw_domain).strip()
    if not domain or domain.lower() == "null":
        return None, ""

    for option in DOMAIN_OPTIONS:
        if domain.lower() == option.lower():
            return option, ""

    lowered = domain.lower()
    for option, aliases in DOMAIN_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return option, ""

    return "Other", domain


def get_structured_questions(extracted: dict | None = None) -> dict:
    """Returns dynamic structured questions with values inferred from the prompt."""
    questions = deepcopy(STRUCTURED_QUESTIONS)
    extracted = extracted or {}

    inferred_domain, custom_domain = _normalize_domain(extracted.get("domain"))

    for question in questions["questions"]:
        qid = question["id"]
        if qid == "domain":
            if inferred_domain:
                question["value"] = inferred_domain
            if custom_domain:
                question["custom_value"] = custom_domain
            continue

        extracted_value = extracted.get(qid)
        if extracted_value:
            question["value"] = extracted_value

    return questions


def build_requirements_spec(initial_input: str, structured_answers: dict, extracted: dict | None = None) -> dict:
    """
    Combines initial prompt + structured answers into a clean requirements specification.

    Args:
        initial_input: The user's original free-text prompt.
        structured_answers: Dict of answered structured questions (id -> value).
        extracted: Any auto-extracted info from the initial prompt.

    Returns:
        Complete requirements spec dict for the Prompt Builder agent.
    """
    logger.info("Lead Agent — building requirements specification")

    domain_answer = structured_answers.get("domain")
    if domain_answer in {"Other", "Custom"}:
        domain_answer = structured_answers.get("domain_custom") or domain_answer
    normalized_domain, _ = _normalize_domain(domain_answer or (extracted.get("domain") if extracted else None))

    entities_answer = structured_answers.get("entities", extracted.get("entities") if extracted else None)
    if isinstance(entities_answer, str):
        parts = [p.strip() for p in re.split(r"[,;\n|/]+", entities_answer) if p and p.strip()]
        entities_answer = ", ".join(parts)

    spec = {
        "original_prompt": initial_input,
        "domain": domain_answer or (extracted.get("domain") if extracted else None),
        "entities": entities_answer,
        "audience": structured_answers.get("audience", "QA / Test Automation"),
        "volume": structured_answers.get("volume", "Medium (1K–10K rows)"),
        "scale_factor": VOLUME_MAP.get(structured_answers.get("volume", "Medium (1K–10K rows)"), 0.1),
        "synthetic_ratio": structured_answers.get("synthetic_ratio", "100% Synthetic"),
        "constraints": structured_answers.get("constraints", extracted.get("constraints") if extracted else None),
        "relationships": structured_answers.get("relationships", extracted.get("relationships") if extracted else None),
    }

    logger.info(f"Lead Agent — spec built: domain={spec['domain']}, volume={spec['volume']}")
    return spec
