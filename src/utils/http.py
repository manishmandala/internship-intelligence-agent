"""
A shared, well-behaved HTTP client for all collectors.

Centralizing this in one place is what gives us, for free, across every
collector:
- a descriptive User-Agent (so a site operator can see who/why is hitting
  their API and has a contact email if something looks wrong)
- automatic retries with exponential backoff for transient failures
  (connection resets, 5xx, 429)
- request timeouts, so a hung connection can't stall a multi-hour run
- a politeness delay between requests to the same host, so we never
  hammer a career site

Collectors should call `get_json()` / `get_text()` rather than using
`requests` directly.
"""
from __future__ import annotations

import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import (
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class RateLimitedSession:
    """A requests.Session wrapper that adds retries, timeouts, and a
    per-host politeness delay between consecutive requests.

    One instance is shared across a collection run so the "last request
    time per host" state is tracked globally, not reset per collector.
    """

    def __init__(
        self,
        delay_seconds: float = REQUEST_DELAY_SECONDS,
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self._last_request_time_by_host: dict[str, float] = {}

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/html;q=0.8, */*;q=0.5",
            }
        )

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1.0,  # 1s, 2s, 4s, ...
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _respect_rate_limit(self, url: str) -> None:
        host = urlparse(url).netloc
        last_time = self._last_request_time_by_host.get(host)
        if last_time is not None:
            elapsed = time.monotonic() - last_time
            wait_for = self.delay_seconds - elapsed
            if wait_for > 0:
                time.sleep(wait_for)
        self._last_request_time_by_host[host] = time.monotonic()

    def get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        self._respect_rate_limit(url)
        return self.session.get(url, params=params, timeout=self.timeout_seconds)

    def post(self, url: str, json_body: Optional[dict] = None) -> requests.Response:
        self._respect_rate_limit(url)
        return self.session.post(url, json=json_body, timeout=self.timeout_seconds)

    def get_json(self, url: str, params: Optional[dict] = None) -> Optional[Any]:
        """GET a URL and parse JSON, returning None (and logging) on any
        failure rather than raising - callers loop over many companies and
        one bad response should never abort the whole run.
        """
        try:
            response = self.get(url, params=params)
        except requests.exceptions.RequestException as exc:
            logger.warning("Request failed for %s: %s", url, exc)
            return None
        return self._parse_json_response(response, url)

    def post_json(self, url: str, json_body: Optional[dict] = None) -> Optional[Any]:
        """POST a JSON body and parse the JSON response, returning None
        (and logging) on any failure rather than raising. Used by sources
        like Workday's CXS API that require a POST search request instead
        of a plain GET.
        """
        try:
            response = self.post(url, json_body=json_body)
        except requests.exceptions.RequestException as exc:
            logger.warning("Request failed for %s: %s", url, exc)
            return None
        return self._parse_json_response(response, url)

    def _parse_json_response(self, response: requests.Response, url: str) -> Optional[Any]:
        if response.status_code == 404:
            logger.info("404 Not Found for %s (source likely misconfigured or moved)", url)
            return None
        if not response.ok:
            logger.warning("Non-OK status %s for %s", response.status_code, url)
            return None

        try:
            return response.json()
        except ValueError as exc:
            logger.warning("Failed to parse JSON from %s: %s", url, exc)
            return None
