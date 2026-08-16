"""
Collector for companies whose career site is backed by Greenhouse and
expose the public job board API at:

    https://boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true

This is the same JSON endpoint the company's own public careers page calls
to render its job list - no authentication, no scraping of rendered HTML.
"""
from __future__ import annotations

from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import JobPosting
from src.parsers.job_parser import build_job_posting
from src.utils.http import RateLimitedSession
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_BOARD_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseCollector(BaseCollector):
    def collect(self, session: RateLimitedSession) -> CollectionResult:
        token = self.company.ats_id
        url = _BOARD_URL_TEMPLATE.format(token=token)

        try:
            data = session.get_json(url, params={"content": "true"})
        except Exception as exc:  # defensive: get_json already catches
            # request errors, but a parsing bug here should never crash a run
            logger.exception("Unexpected error collecting %s (Greenhouse)", self.company.name)
            return CollectionResult(self.company.name, "greenhouse", False, error=str(exc))

        if data is None:
            return CollectionResult(
                self.company.name, "greenhouse", False,
                error=f"No response / non-JSON from board '{token}'.",
            )

        raw_jobs = data.get("jobs", [])
        jobs: list[JobPosting] = []
        for raw in raw_jobs:
            try:
                job = self._parse_job(raw)
                if job:
                    jobs.append(job)
            except Exception:
                logger.exception(
                    "Failed to parse a Greenhouse job for %s (job id=%s)",
                    self.company.name, raw.get("id"),
                )

        logger.info(
            "%s (Greenhouse): %d total postings, %d matched as internship/co-op",
            self.company.name, len(raw_jobs), len(jobs),
        )
        return CollectionResult(self.company.name, "greenhouse", True, jobs=jobs)

    def _parse_job(self, raw: dict) -> JobPosting | None:
        title = raw.get("title", "")
        url = raw.get("absolute_url", "")
        location = (raw.get("location") or {}).get("name", "Unknown")
        departments = raw.get("departments") or []
        department = departments[0]["name"] if departments else ""
        content_html = raw.get("content", "")
        posted_date = raw.get("first_published")
        application_deadline = raw.get("application_deadline")

        return build_job_posting(
            company=self.company.name,
            title=title,
            url=url,
            source="greenhouse",
            location=location,
            description_html=content_html,
            department=department,
            posted_date=posted_date,
            application_deadline=application_deadline,
            industry_hint=self.company.industry if self.company.industry != "other" else None,
        )
