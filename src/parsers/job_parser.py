"""
Turns raw, source-specific fields into a normalized JobPosting.

Source-specific parsers (greenhouse_parser.py, lever_parser.py,
amazon_parser.py) each pull the right fields out of that source's JSON
shape and hand off to `build_job_posting()` here, so the cleaning,
classification, and skills-extraction logic is written exactly once.
"""
from __future__ import annotations

import re
from typing import Optional

from src.analysis.skills import extract_skills
from src.database.models import JobPosting
from src.parsers.classifiers import classify_industry, classify_role_category
from src.parsers.text_utils import (
    classify_employment_type,
    html_to_text,
    split_qualifications,
)
from src.utils.dedup import compute_job_hash
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


# Word-boundary matching is essential here: a plain substring check for
# "intern" also matches "Internal", "International", "Internet", etc,
# which silently pollutes results with unrelated full-time roles.
_INTERNSHIP_TITLE_PATTERN = re.compile(
    r"\b(intern|interns|internship|internships|co-op|co-ops|coop|coops|co\s+op)\b",
    re.IGNORECASE,
)


def is_internship_posting(title: str) -> bool:
    """Title-only pre-filter. Company job boards list every open role
    (full-time, internship, etc.) - we only want internship/co-op
    postings, and rely on the scoring engine (not this filter) to judge
    how relevant each one is to the candidate's interests.
    """
    return bool(_INTERNSHIP_TITLE_PATTERN.search(title))


def build_job_posting(
    *,
    company: str,
    title: str,
    url: str,
    source: str,
    location: str,
    description_html: str = "",
    description_text: str = "",
    department: str = "",
    posted_date: Optional[str] = None,
    application_deadline: Optional[str] = None,
    industry_hint: Optional[str] = None,
) -> Optional[JobPosting]:
    """Build a JobPosting from already-extracted raw fields.

    Returns None if this doesn't look like an internship/co-op posting -
    callers should skip it rather than storing it.

    `description_html` is cleaned via BeautifulSoup; pass `description_text`
    instead if the source already gives plain text (e.g. Lever's
    `descriptionPlain`) to skip that step.
    """
    if not title or not url or not company:
        logger.debug("Skipping malformed posting (missing title/url/company)")
        return None

    if not is_internship_posting(title):
        return None

    full_text = description_text.strip() if description_text else html_to_text(description_html)
    required_text, preferred_text = split_qualifications(full_text)
    # Fall back to matching against the whole description if we couldn't
    # find explicit section headings - better to over-match skills than
    # miss them entirely.
    skill_search_text = full_text if not required_text else f"{required_text}\n{preferred_text}"

    role_category = classify_role_category(title, full_text)
    industry_category = industry_hint or classify_industry(company, title, full_text)
    employment_type = classify_employment_type(title, full_text)
    required_skills = extract_skills(skill_search_text)

    job_hash = compute_job_hash(company=company, title=title, location=location, url=url)

    return JobPosting(
        company=company,
        title=title.strip(),
        url=url,
        source=source,
        job_hash=job_hash,
        location=location or "Unknown",
        employment_type=employment_type,
        department=department,
        industry_category=industry_category,
        role_category=role_category,
        description=full_text,
        qualifications=required_text,
        preferred_qualifications=preferred_text,
        required_skills=required_skills,
        posted_date=posted_date,
        application_deadline=application_deadline,
    )
