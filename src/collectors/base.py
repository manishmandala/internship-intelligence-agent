"""
Collector interface.

Every source (Greenhouse, Lever, a future company-specific collector, ...)
implements `BaseCollector.collect()` and returns a `CollectionResult`. This
is the contract that lets `src/main.py` iterate over an arbitrary list of
collectors without knowing anything about how each one talks to its source,
and lets one failing collector never take down the whole run.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from config.companies import CompanySource
from src.database.models import JobPosting
from src.utils.http import RateLimitedSession


@dataclass
class CollectionResult:
    company: str
    source: str
    success: bool
    jobs: list[JobPosting] = field(default_factory=list)
    error: str = ""


class BaseCollector(ABC):
    """Base class for a single company's/source's collector."""

    def __init__(self, company: CompanySource) -> None:
        self.company = company

    @abstractmethod
    def collect(self, session: RateLimitedSession) -> CollectionResult:
        """Fetch and parse this source's current postings.

        Implementations MUST catch their own exceptions and return a
        CollectionResult with success=False and a useful `error` message
        rather than raising - the orchestrator treats an uncaught
        exception as a bug, not an expected "this source failed".
        """
        raise NotImplementedError
