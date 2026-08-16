"""
Scoring engine.

`BaseScorer` defines the interface every scoring backend must implement.
`RuleBasedScorer` is a weighted-keyword/eligibility implementation that
needs no external API and no API key. A future LLM-backed scorer (e.g.
`LLMScorer`) can be added later by implementing the same `score()` method
and swapping which one `src/main.py` instantiates - nothing else in the
project needs to change.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from config.keywords import HIGH_VALUE_SKILLS, SELECTIVE_SIGNAL_PHRASES
from config.settings import CANDIDATE_PROFILE
from src.database.models import JobPosting
from src.scoring.location import classify_us_location
from src.scoring.rules import (
    GRAD_YEAR_SEARCH_RANGE,
    HIGH_VALUE_FLAG_THRESHOLD,
    INDUSTRY_FIT_SCORES,
    ROLE_FIT_SCORES,
    SCORE_WEIGHTS,
    TIME_SENSITIVE_DEADLINE_DAYS,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_GRAD_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


class BaseScorer(ABC):
    """Interface every scoring backend implements."""

    @abstractmethod
    def score(self, job: JobPosting) -> JobPosting:
        """Populate `job`'s scoring fields (fit_score, sub-scores,
        score_explanation, is_flagged, flag_reasons) and return it.
        """
        raise NotImplementedError


class RuleBasedScorer(BaseScorer):
    """Weighted keyword-and-eligibility scoring. No external API calls."""

    def __init__(self, candidate_grad_year: int = CANDIDATE_PROFILE["graduation_year"]) -> None:
        self.candidate_grad_year = candidate_grad_year

    def score(self, job: JobPosting) -> JobPosting:
        role_score, role_reason = self._score_role_fit(job)
        industry_score, industry_reason = self._score_industry_fit(job)
        eligibility_score, eligibility_reason = self._score_eligibility_fit(job)
        skills_score, skills_reason = self._score_skills_fit(job)
        location_score, location_reason = self._score_location_fit(job)

        overall = (
            role_score * SCORE_WEIGHTS["role_fit"]
            + industry_score * SCORE_WEIGHTS["industry_fit"]
            + eligibility_score * SCORE_WEIGHTS["eligibility_fit"]
            + skills_score * SCORE_WEIGHTS["skills_fit"]
            + location_score * SCORE_WEIGHTS["location_fit"]
        )

        job.score_role_fit = round(role_score)
        job.score_industry_fit = round(industry_score)
        job.score_eligibility_fit = round(eligibility_score)
        job.score_skills_fit = round(skills_score)
        job.score_location_fit = round(location_score)
        job.fit_score = round(overall)
        job.score_explanation = json.dumps(
            {
                "overall_fit": f"{job.fit_score}/100",
                "role_fit": role_reason,
                "industry_fit": industry_reason,
                "eligibility_fit": eligibility_reason,
                "skills_fit": skills_reason,
                "location_fit": location_reason,
            }
        )

        job.is_flagged, job.flag_reasons = self._determine_flags(job)
        return job

    # --- sub-scores ------------------------------------------------

    def _score_role_fit(self, job: JobPosting) -> tuple[float, str]:
        score = ROLE_FIT_SCORES.get(job.role_category, ROLE_FIT_SCORES["other"])
        readable_category = job.role_category.replace("_", " ")
        reason = f"Title/description matched role category '{readable_category}'."
        return score, reason

    def _score_industry_fit(self, job: JobPosting) -> tuple[float, str]:
        score = INDUSTRY_FIT_SCORES.get(job.industry_category, INDUSTRY_FIT_SCORES["other"])
        readable_category = job.industry_category.replace("_", " ")
        reason = f"Company/description matched industry '{readable_category}'."
        return score, reason

    def _score_eligibility_fit(self, job: JobPosting) -> tuple[float, str]:
        text = f"{job.qualifications} {job.preferred_qualifications} {job.description}"
        mentioned_years = self._extract_grad_years(text)

        if not mentioned_years:
            if "rising senior" in text.lower() and "rising junior" not in text.lower():
                return 50.0, "No explicit grad years found, but posting suggests rising seniors preferred."
            if "rising junior" in text.lower() or "rising sophomore" in text.lower():
                return 70.0, "No explicit grad years found; posting welcomes underclassmen."
            return 75.0, "No explicit graduation-year requirement found in the posting."

        if self.candidate_grad_year in mentioned_years:
            return 100.0, f"Posting explicitly lists {self.candidate_grad_year} as an eligible graduation year."

        if max(mentioned_years) < self.candidate_grad_year:
            gap = self.candidate_grad_year - max(mentioned_years)
            score = max(15.0, 70.0 - gap * 15)
            return score, (
                f"Posting targets graduation years up to {max(mentioned_years)}, "
                f"{gap} year(s) before candidate's {self.candidate_grad_year} graduation."
            )

        if min(mentioned_years) <= self.candidate_grad_year <= max(mentioned_years):
            return 90.0, (
                f"Candidate's {self.candidate_grad_year} graduation falls within the "
                f"posting's mentioned range ({min(mentioned_years)}-{max(mentioned_years)})."
            )

        gap = min(mentioned_years) - self.candidate_grad_year
        score = max(15.0, 70.0 - gap * 15)
        return score, (
            f"Posting targets graduation years starting {min(mentioned_years)}, "
            f"{gap} year(s) after candidate's {self.candidate_grad_year} graduation."
        )

    def _score_skills_fit(self, job: JobPosting) -> tuple[float, str]:
        if not job.required_skills:
            return 55.0, "No specific technical skills were detected in the posting text."

        high_value_hits = [s for s in job.required_skills if s in HIGH_VALUE_SKILLS]
        ratio = len(high_value_hits) / len(job.required_skills)
        score = 40 + ratio * 60  # 40..100 depending on how many are high-value
        reason = (
            f"Detected skills: {', '.join(job.required_skills)}. "
            f"{len(high_value_hits)}/{len(job.required_skills)} are high-value for this profile."
        )
        return score, reason

    def _score_location_fit(self, job: JobPosting) -> tuple[float, str]:
        classification = classify_us_location(job.location)
        if classification == "us":
            return 100.0, f"Location '{job.location}' identified as within the United States."
        if classification == "non_us":
            return 0.0, f"Location '{job.location}' identified as outside the United States."
        return 55.0, f"Location '{job.location}' could not be confidently classified; treated as neutral."

    # --- flags -------------------------------------------------------

    def _determine_flags(self, job: JobPosting) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        if job.fit_score >= HIGH_VALUE_FLAG_THRESHOLD:
            reasons.append(f"High overall fit score ({job.fit_score}/100).")

        text = f"{job.description} {job.qualifications}".lower()
        if any(phrase in text for phrase in SELECTIVE_SIGNAL_PHRASES):
            reasons.append("Posting language suggests a selective/competitive program.")

        deadline = self._parse_deadline(job.application_deadline)
        if deadline:
            days_remaining = (deadline - datetime.now(timezone.utc)).days
            if 0 <= days_remaining <= TIME_SENSITIVE_DEADLINE_DAYS:
                reasons.append(f"Application deadline in {days_remaining} day(s).")

        return (len(reasons) > 0, reasons)

    # --- helpers -------------------------------------------------------

    def _extract_grad_years(self, text: str) -> list[int]:
        low, high = GRAD_YEAR_SEARCH_RANGE
        years = {int(y) for y in _GRAD_YEAR_PATTERN.findall(text)}
        return sorted(y for y in years if low <= y <= high)

    def _parse_deadline(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
