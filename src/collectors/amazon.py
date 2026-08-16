"""
Collector for Amazon, using the public JSON search API that
amazon.jobs itself calls to render search results:

    https://www.amazon.jobs/en/search.json?base_query=<text>&result_limit=<n>&offset=<n>

No authentication, no scraping of rendered HTML - this returns the same
structured data the public search page displays. Amazon does not run on
Greenhouse/Lever, so this collector is company-specific rather than
built on the generic ATS collectors.
"""
from __future__ import annotations

from datetime import datetime

from config.keywords import SEARCH_KEYWORDS
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import JobPosting
from src.parsers.job_parser import build_job_posting
from src.utils.http import RateLimitedSession
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_SEARCH_URL = "https://www.amazon.jobs/en/search.json"
_RESULT_LIMIT = 20


class AmazonCollector(BaseCollector):
    def collect(self, session: RateLimitedSession) -> CollectionResult:
        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()
        any_query_succeeded = False
        errors: list[str] = []

        for keyword in SEARCH_KEYWORDS:
            data = session.get_json(
                _SEARCH_URL,
                params={"base_query": keyword, "result_limit": _RESULT_LIMIT, "offset": 0},
            )
            if data is None:
                errors.append(f"query '{keyword}' failed")
                continue
            any_query_succeeded = True

            for raw in data.get("jobs", []):
                job_id = raw.get("id_icims") or raw.get("id")
                if not job_id or job_id in seen_ids:
                    continue
                if raw.get("country_code") != "USA":
                    continue
                seen_ids.add(job_id)
                try:
                    job = self._parse_job(raw)
                    if job:
                        jobs.append(job)
                except Exception:
                    logger.exception("Failed to parse an Amazon job (id=%s)", job_id)

        if not any_query_succeeded:
            return CollectionResult(
                self.company.name, "amazon_jobs_api", False,
                error=f"All {len(SEARCH_KEYWORDS)} search queries failed: {'; '.join(errors[:3])}",
            )

        logger.info(
            "%s (amazon_jobs_api): %d unique US postings matched as internship/co-op",
            self.company.name, len(jobs),
        )
        return CollectionResult(self.company.name, "amazon_jobs_api", True, jobs=jobs)

    def _parse_job(self, raw: dict) -> JobPosting | None:
        title = raw.get("title", "")
        job_path = raw.get("job_path", "")
        url = f"https://www.amazon.jobs{job_path}" if job_path else ""
        location = raw.get("normalized_location", "Unknown")
        department = raw.get("job_category", "")

        description = raw.get("description", "") or ""
        basic_qual = raw.get("basic_qualifications", "") or ""
        preferred_qual = raw.get("preferred_qualifications", "") or ""
        combined_html = (
            f"{description}<br/><br/><b>Basic Qualifications</b><br/>{basic_qual}"
            f"<br/><br/><b>Preferred Qualifications</b><br/>{preferred_qual}"
        )

        posted_date = self._parse_posted_date(raw.get("posted_date"))

        return build_job_posting(
            company=self.company.name,
            title=title,
            url=url,
            source="amazon_jobs_api",
            location=location,
            description_html=combined_html,
            department=department,
            posted_date=posted_date,
            application_deadline=None,  # not exposed by this API
            industry_hint=self.company.industry if self.company.industry != "other" else None,
        )

    def _parse_posted_date(self, raw_date: str | None) -> str | None:
        if not raw_date:
            return None
        try:
            return datetime.strptime(raw_date, "%B %d, %Y").date().isoformat()
        except ValueError:
            return None
