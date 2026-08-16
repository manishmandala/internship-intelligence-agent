"""
Collector for companies whose career site is backed by Ashby and expose the
public job board API at:

    https://api.ashbyhq.com/posting-api/job-board/<board_name>

This is Ashby's own documented public posting API (no authentication) -
the same data source Ashby-hosted career pages themselves render from.
"""
from __future__ import annotations

from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import JobPosting
from src.parsers.job_parser import build_job_posting
from src.utils.http import RateLimitedSession
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_BOARD_URL_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"


class AshbyCollector(BaseCollector):
    def collect(self, session: RateLimitedSession) -> CollectionResult:
        board_name = self.company.ats_id
        url = _BOARD_URL_TEMPLATE.format(board_name=board_name)

        data = session.get_json(url)
        if data is None:
            return CollectionResult(
                self.company.name, "ashby", False,
                error=f"No response / non-JSON from Ashby board '{board_name}'.",
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
                    "Failed to parse an Ashby job for %s (job id=%s)",
                    self.company.name, raw.get("id"),
                )

        logger.info(
            "%s (Ashby): %d total postings, %d matched as internship/co-op",
            self.company.name, len(raw_jobs), len(jobs),
        )
        return CollectionResult(self.company.name, "ashby", True, jobs=jobs)

    def _parse_job(self, raw: dict) -> JobPosting | None:
        title = raw.get("title", "")
        url = raw.get("jobUrl") or raw.get("applyUrl", "")
        location = raw.get("location", "Unknown")
        department = raw.get("department") or raw.get("team") or ""
        description_html = raw.get("descriptionHtml", "")
        posted_date = raw.get("publishedAt")

        # Not every posting includes structured address info, but when it
        # does, prefer the country name for US detection over the free-text
        # `location` field (which is sometimes just a city).
        address = (raw.get("address") or {}).get("postalAddress") or {}
        country = address.get("addressCountry")
        if country:
            location = f"{location}, {country}" if location and location != "Unknown" else country

        return build_job_posting(
            company=self.company.name,
            title=title,
            url=url,
            source="ashby",
            location=location,
            description_html=description_html,
            department=department,
            posted_date=posted_date,
            application_deadline=None,  # not exposed by this API
            industry_hint=self.company.industry if self.company.industry != "other" else None,
        )
