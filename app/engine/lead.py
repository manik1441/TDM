"""
Lead Agent — Data-domain gatekeeper and intake specialist.

Responsibilities:
- Validates that user input is data-related (rejects off-topic requests)
- Asks structured follow-up questions with dropdown options
- Produces a clean, structured requirements spec for the Prompt Builder
"""

"""
Validates user intent, collects structured inputs, infers and normalizes domain, 
suggests core tables, and builds a clean requirements specification. 
It prepares authoritative fields like entities, volume, constraints, 
and relationships so downstream generation receives consistent, 
backend-safe inputs from form answers and extracted prompt context, 
with sensible defaults and fallbacks.
"""

import json
import re
from copy import deepcopy
from app.config import get_llm_config
from app.llm import run_markdown_agent
from app.logger import get_logger

logger = get_logger(__name__)

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
        result = json.loads(response)
        logger.info(f"Lead Agent — validation result: valid={result.get('is_valid')}, followup={result.get('needs_followup')}")
        return result
    except json.JSONDecodeError:
        logger.error(f"Lead Agent — failed to parse LLM response: {response[:200]}")
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
