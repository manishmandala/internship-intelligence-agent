"""
Collector for companies whose career site runs on Workday.

Workday-hosted career pages (e.g. jobs.boeing.com) are a JavaScript app
that itself calls a public, unauthenticated JSON search API - the same one
this collector uses:

    POST https://<tenant>.<wdHost>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs
    GET  https://<tenant>.<wdHost>.myworkdayjobs.com/wday/cxs/<tenant>/<site><externalPath>

No authentication, no scraping of rendered HTML - this is the exact data
the public career site's own search box uses. `<tenant>/<wdHost>/<site>`
for each company was found by loading that company's real public careers
page and reading out the myworkdayjobs.com URL it embeds, then confirmed
by directly querying this API and checking for real job data.

Workday's search is fairly noisy full-text search (matches "intern"
anywhere in a posting, not just the title), so this collector searches
broadly then relies on the same title-based internship filter as every
other collector to discard the noise.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

from config.companies import CompanySource
from src.collectors.base import BaseCollector, CollectionResult
from src.database.models import JobPosting
from src.parsers.job_parser import build_job_posting, is_internship_posting
from src.utils.http import RateLimitedSession
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_PAGE_SIZE = 20  # Workday's CXS API rejects limit values above 20.
_MAX_PAGES = 3  # search up to 60 results deep per company
_MAX_DETAIL_FETCHES = 30  # cap per-job detail requests per company per run

_RELATIVE_DATE_PATTERN = re.compile(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", re.IGNORECASE)


def _parse_relative_posted_date(text: Optional[str]) -> Optional[str]:
    """Workday reports posting age as relative text like 'Posted 7 Days
    Ago' rather than an absolute date. Converts that to an approximate
    ISO date; returns None if the text doesn't match a known pattern.
    """
    if not text:
        return None
    match = _RELATIVE_DATE_PATTERN.search(text)
    if not match:
        return None
    phrase = match.group(1).lower()
    if phrase == "today":
        days_ago = 0
    elif phrase == "yesterday":
        days_ago = 1
    else:
        days_ago = int(match.group(2))
    return (date.today() - timedelta(days=days_ago)).isoformat()


class WorkdayCollector(BaseCollector):
    def __init__(self, company: CompanySource) -> None:
        super().__init__(company)
        tenant, wd_host, site = company.ats_id.split("/")
        self.tenant = tenant
        self.wd_host = wd_host
        self.site = site
        self.base_url = f"https://{tenant}.{wd_host}.myworkdayjobs.com"
        self.search_url = f"{self.base_url}/wday/cxs/{tenant}/{site}/jobs"

    def collect(self, session: RateLimitedSession) -> CollectionResult:
        candidates = self._search_candidates(session)
        if candidates is None:
            return CollectionResult(
                self.company.name, "workday", False,
                error=f"Workday search failed for tenant '{self.tenant}'.",
            )

        title_matches = [c for c in candidates if is_internship_posting(c.get("title", ""))]
        title_matches = title_matches[:_MAX_DETAIL_FETCHES]

        jobs: list[JobPosting] = []
        for candidate in title_matches:
            try:
                job = self._fetch_and_parse_detail(session, candidate)
                if job:
                    jobs.append(job)
            except Exception:
                logger.exception(
                    "Failed to parse a Workday job detail for %s (%s)",
                    self.company.name, candidate.get("title"),
                )

        logger.info(
            "%s (Workday): %d candidates searched, %d title-matched, %d fully parsed",
            self.company.name, len(candidates), len(title_matches), len(jobs),
        )
        return CollectionResult(self.company.name, "workday", True, jobs=jobs)

    def _search_candidates(self, session: RateLimitedSession) -> Optional[list[dict]]:
        all_postings: list[dict] = []
        for page in range(_MAX_PAGES):
            data = session.post_json(
                self.search_url,
                json_body={
                    "appliedFacets": {},
                    "limit": _PAGE_SIZE,
                    "offset": page * _PAGE_SIZE,
                    "searchText": "intern",
                },
            )
            if data is None:
                # First page failing means the source is down/misconfigured;
                # a later page failing just means we stop early with what
                # we already have.
                return None if page == 0 else all_postings

            postings = data.get("jobPostings", [])
            all_postings.extend(postings)
            if len(postings) < _PAGE_SIZE:
                break  # no more results
        return all_postings

    def _fetch_and_parse_detail(self, session: RateLimitedSession, candidate: dict) -> Optional[JobPosting]:
        external_path = candidate.get("externalPath", "")
        detail_url = f"{self.base_url}/wday/cxs/{self.tenant}/{self.site}{external_path}"
        detail = session.get_json(detail_url)
        if detail is None:
            return None

        info = detail.get("jobPostingInfo", {})
        title = info.get("title", candidate.get("title", ""))
        url = info.get("externalUrl", "")
        location = info.get("location", "Unknown")
        description_html = info.get("jobDescription", "")
        posted_date = _parse_relative_posted_date(info.get("postedOn"))
        application_deadline = info.get("endDate")  # already ISO (YYYY-MM-DD) when present

        return build_job_posting(
            company=self.company.name,
            title=title,
            url=url,
            source="workday",
            location=location,
            description_html=description_html,
            posted_date=posted_date,
            application_deadline=application_deadline,
            industry_hint=self.company.industry if self.company.industry != "other" else None,
        )
