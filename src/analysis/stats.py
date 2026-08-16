"""
Summary statistics computed over the stored jobs, shared by the CLI
end-of-run summary and the Streamlit dashboard's "Insights" section.

Everything here takes the list-of-dicts shape returned by
`src.database.repository.get_all_jobs()` so it has no database dependency
of its own and is easy to unit test with plain Python data.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any


def top_companies(jobs: list[dict[str, Any]], limit: int = 10) -> list[tuple[str, int]]:
    counts = Counter(job["company"] for job in jobs)
    return counts.most_common(limit)


def top_skills(jobs: list[dict[str, Any]], limit: int = 15) -> list[tuple[str, int]]:
    counts: Counter = Counter()
    for job in jobs:
        counts.update(job.get("required_skills", []))
    return counts.most_common(limit)


def top_skills_in_high_fit_roles(
    jobs: list[dict[str, Any]], min_score: int = 70, limit: int = 15
) -> list[tuple[str, int]]:
    high_fit = [j for j in jobs if j.get("fit_score", 0) >= min_score]
    return top_skills(high_fit, limit=limit)


def highest_fit_opportunities(jobs: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return sorted(jobs, key=lambda j: j.get("fit_score", 0), reverse=True)[:limit]


def newly_discovered(jobs: list[dict[str, Any]], within_days: int = 3, limit: int = 20) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    recent = []
    for job in jobs:
        found = _parse_iso(job.get("date_found"))
        if found and found >= cutoff:
            recent.append(job)
    return sorted(recent, key=lambda j: j.get("date_found", ""), reverse=True)[:limit]


def approaching_deadlines(jobs: list[dict[str, Any]], within_days: int = 14, limit: int = 20) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=within_days)
    upcoming = []
    for job in jobs:
        deadline = _parse_iso(job.get("application_deadline"))
        if deadline and now <= deadline <= cutoff:
            upcoming.append(job)
    return sorted(upcoming, key=lambda j: j.get("application_deadline", ""))[:limit]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def summary_report(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """A compact dict suitable for printing at the end of a collection run."""
    active_jobs = [j for j in jobs if j.get("is_active", True)]
    flagged_jobs = [j for j in jobs if j.get("is_flagged")]
    return {
        "total_jobs": len(jobs),
        "active_jobs": len(active_jobs),
        "flagged_jobs": len(flagged_jobs),
        "average_fit_score": round(
            sum(j.get("fit_score", 0) for j in jobs) / len(jobs), 1
        ) if jobs else 0,
        "top_companies": top_companies(jobs, limit=5),
        "top_skills": top_skills(jobs, limit=10),
        "highest_fit": [
            (j["company"], j["title"], j["fit_score"]) for j in highest_fit_opportunities(jobs, limit=5)
        ],
    }
