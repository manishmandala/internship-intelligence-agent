"""
Collector for companies whose career site is backed by Lever and expose the
public postings API at:

    https://api.lever.co/v0/postings/<company>?mode=json

Same reasoning as the Greenhouse collector: this is Lever's own public,
structured, unauthenticated JSON API.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import JobPosting
from src.parsers.job_parser import build_job_posting
from src.utils.http import RateLimitedSession
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_POSTINGS_URL_TEMPLATE = "https://api.lever.co/v0/postings/{company}"


class LeverCollector(BaseCollector):
    def collect(self, session: RateLimitedSession) -> CollectionResult:
        company_slug = self.company.ats_id
        url = _POSTINGS_URL_TEMPLATE.format(company=company_slug)

        data = session.get_json(url, params={"mode": "json"})

        if data is None:
            return CollectionResult(
                self.company.name, "lever", False,
                error=f"No response / non-JSON from Lever company '{company_slug}'.",
            )

        raw_jobs = data if isinstance(data, list) else []
        jobs: list[JobPosting] = []
        for raw in raw_jobs:
            try:
                job = self._parse_job(raw)
                if job:
                    jobs.append(job)
            except Exception:
                logger.exception(
                    "Failed to parse a Lever job for %s (job id=%s)",
                    self.company.name, raw.get("id"),
                )

        logger.info(
            "%s (Lever): %d total postings, %d matched as internship/co-op",
            self.company.name, len(raw_jobs), len(jobs),
        )
        return CollectionResult(self.company.name, "lever", True, jobs=jobs)

    def _parse_job(self, raw: dict) -> JobPosting | None:
        title = raw.get("text", "")
        url = raw.get("hostedUrl", "")
        categories = raw.get("categories") or {}
        location = categories.get("location", "Unknown")
        department = categories.get("team", "")
        description_text = raw.get("descriptionPlain", "") or ""

        posted_date = None
        created_at_ms = raw.get("createdAt")
        if isinstance(created_at_ms, (int, float)):
            posted_date = datetime.fromtimestamp(
                created_at_ms / 1000, tz=timezone.utc
            ).isoformat(timespec="seconds")

        return build_job_posting(
            company=self.company.name,
            title=title,
            url=url,
            source="lever",
            location=location,
            description_text=description_text,
            department=department,
            posted_date=posted_date,
            application_deadline=None,  # Lever's public API does not expose this
            industry_hint=self.company.industry if self.company.industry != "other" else None,
        )
