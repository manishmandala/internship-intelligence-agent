"""
Data models shared across the collection -> parsing -> scoring -> storage
pipeline.

`JobPosting` is intentionally a plain dataclass (not tied to SQLite) so
parsers and the scorer can build/inspect it without importing the database
layer. `database/repository.py` is the only place that knows how to turn
one into/from SQLite rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class JobPosting:
    """A normalized internship/co-op posting, ready to be scored and stored."""

    # Identity / source
    company: str
    title: str
    url: str
    source: str  # "greenhouse" | "lever" | "amazon_jobs_api" | ...
    job_hash: str = ""  # computed by src.utils.dedup.compute_job_hash

    # Core fields
    location: str = "Unknown"
    employment_type: str = "Unknown"  # "Internship" | "Co-op" | "Unknown"
    department: str = ""
    industry_category: str = "other"
    role_category: str = "other"

    # Content
    description: str = ""
    qualifications: str = ""
    preferred_qualifications: str = ""
    required_skills: list[str] = field(default_factory=list)

    # Dates (ISO 8601 strings, or None if unknown)
    posted_date: Optional[str] = None
    application_deadline: Optional[str] = None
    date_found: str = field(default_factory=utc_now_iso)
    last_checked: str = field(default_factory=utc_now_iso)

    # Scoring (populated by src.scoring.scorer)
    fit_score: int = 0
    score_role_fit: int = 0
    score_industry_fit: int = 0
    score_eligibility_fit: int = 0
    score_skills_fit: int = 0
    score_location_fit: int = 0
    score_explanation: str = ""  # JSON-encoded dict of human-readable reasons

    # Flags
    is_flagged: bool = False
    flag_reasons: list[str] = field(default_factory=list)

    # User-tracked workflow state (not touched by the collector on update)
    status: str = "new"  # new|interested|applied|interviewing|rejected|offer|ignored
    notes: str = ""

    # Row bookkeeping
    id: Optional[int] = None
    is_active: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


STATUS_VALUES = [
    "new",
    "interested",
    "applied",
    "interviewing",
    "rejected",
    "offer",
    "ignored",
]
