"""
Sanity tests for config/companies.py itself.

test_no_duplicate_company_names is a regression test: adding a new,
supported entry for a company that already had an "unsupported" row (e.g.
when Boeing's Workday collector was added) without removing the old row
left both in the list. `_select_companies()` in src/main.py matches by
name, so a duplicate caused the company to be simultaneously logged as
"no supported collector, skipping" AND actually collected in the same run.
"""
from __future__ import annotations

from collections import Counter

from config.companies import COMPANIES, active_companies, unsupported_companies


def test_no_duplicate_company_names():
    names = [c.name for c in COMPANIES]
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    assert duplicates == [], f"Duplicate company entries found: {duplicates}"


def test_every_company_is_active_or_unsupported_not_both():
    active_names = {c.name for c in active_companies()}
    unsupported_names = {c.name for c in unsupported_companies()}
    assert active_names.isdisjoint(unsupported_names)
    assert active_names | unsupported_names == {c.name for c in COMPANIES}


def test_active_companies_have_an_ats_id():
    for company in active_companies():
        assert company.ats_id, f"{company.name} is active but has no ats_id"


def test_workday_ats_id_has_three_parts():
    for company in active_companies():
        if company.ats == "workday":
            parts = company.ats_id.split("/")
            assert len(parts) == 3, f"{company.name}'s workday ats_id should be 'tenant/host/site', got {company.ats_id!r}"
