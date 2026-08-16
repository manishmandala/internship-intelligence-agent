"""
Maps a CompanySource's `ats` value to the collector class that knows how to
handle it, and builds the list of collectors to run for a collection cycle.

Adding a new company that already uses Greenhouse or Lever requires no new
code - just add an entry to config/companies.py. Adding a brand-new
company-specific source (like Amazon) means writing one collector class
and registering it here.
"""
from __future__ import annotations

from config.companies import CompanySource, active_companies
from src.collectors.amazon import AmazonCollector
from src.collectors.ashby import AshbyCollector
from src.collectors.base import BaseCollector
from src.collectors.greenhouse import GreenhouseCollector
from src.collectors.lever import LeverCollector
from src.collectors.workday import WorkdayCollector
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_COLLECTOR_CLASSES: dict[str, type[BaseCollector]] = {
    "greenhouse": GreenhouseCollector,
    "lever": LeverCollector,
    "amazon_jobs_api": AmazonCollector,
    "ashby": AshbyCollector,
    "workday": WorkdayCollector,
}


def build_collectors(companies: list[CompanySource] | None = None) -> list[BaseCollector]:
    """Instantiate one collector per active (supported) company.

    `companies` defaults to every company in config/companies.py whose
    `ats` is not "unsupported". Pass a subset for testing/manual runs.
    """
    companies = companies if companies is not None else active_companies()

    collectors: list[BaseCollector] = []
    for company in companies:
        collector_cls = _COLLECTOR_CLASSES.get(company.ats)
        if collector_cls is None:
            logger.warning(
                "No collector registered for ats='%s' (company=%s); skipping.",
                company.ats, company.name,
            )
            continue
        collectors.append(collector_cls(company))
    return collectors
