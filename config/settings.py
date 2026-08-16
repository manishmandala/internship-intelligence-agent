"""
Central configuration for the Internship Intelligence Agent.

Values here are loaded from environment variables (via a `.env` file, see
`.env.example`) with sensible defaults so the project runs out of the box.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root if present. This does nothing (and does not
# error) if no .env file exists, which keeps "works out of the box" true.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- Paths -------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / os.getenv("IIA_LOG_DIR", "logs")
DB_PATH = PROJECT_ROOT / os.getenv("IIA_DB_PATH", "data/internships.db")

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Networking / politeness --------------------------------------------
REQUEST_DELAY_SECONDS = _env_float("IIA_REQUEST_DELAY_SECONDS", 1.5)
REQUEST_TIMEOUT_SECONDS = _env_int("IIA_REQUEST_TIMEOUT_SECONDS", 15)
MAX_RETRIES = _env_int("IIA_MAX_RETRIES", 3)
CONTACT_EMAIL = os.getenv("IIA_CONTACT_EMAIL", "not-provided@example.com")

USER_AGENT = (
    f"InternshipIntelligenceAgent/1.0 "
    f"(personal internship search tool; contact: {CONTACT_EMAIL})"
)

# --- Candidate profile ---------------------------------------------------
# This describes the person the scoring engine is optimizing for. Editing
# this dict is the primary way to re-target the whole project at a different
# student without touching scoring logic.
CANDIDATE_PROFILE = {
    "school": "Ohio State University",
    "major": "Mechanical Engineering",
    "graduation_year": 2029,
    "current_year_estimate": "freshman",  # 2029 grad in 2026 => rising sophomore
    "target_locations": ["United States"],  # willing to work anywhere in the US
    "interest_areas": [
        "mechanical engineering",
        "design engineering",
        "manufacturing engineering",
        "product management",
        "program management",
        "technical consulting",
        "management consulting",
        "tech strategy",
        "ai",
        "robotics",
        "deep tech",
        "energy",
        "industrial equipment",
        "medical devices",
        "consumer hardware",
        "aerospace",
        "defense",
        "automotive",
        "electric vehicles",
    ],
}

# Internship recruiting typically targets rising sophomores/juniors/seniors.
# A 2029 grad is a very early-career candidate; eligibility scoring treats
# "no explicit year requirement" as neutral rather than penalizing.
ELIGIBLE_GRAD_YEAR_RANGE = (2027, 2030)
