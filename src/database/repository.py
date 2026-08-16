"""
All SQL for the `jobs` table lives here. Nothing outside this module should
write raw SQL against the jobs table - that keeps the dedup/upsert logic in
exactly one place.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from src.database.db import db_transaction, get_connection
from src.database.models import JobPosting, utc_now_iso
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Fields that come from the source (career site) and should always be
# refreshed when we see a posting again. Deliberately excludes user-owned
# fields (status, notes) and first-seen bookkeeping (date_found, created_at)
# so a re-collection never clobbers what the user has done with a posting.
_REFRESHABLE_FIELDS = [
    "title", "url", "location", "employment_type", "department",
    "industry_category", "role_category", "description", "qualifications",
    "preferred_qualifications", "required_skills", "posted_date",
    "application_deadline", "last_checked", "fit_score", "score_role_fit",
    "score_industry_fit", "score_eligibility_fit", "score_skills_fit",
    "score_location_fit", "score_explanation", "is_flagged", "flag_reasons",
    "is_active", "updated_at",
]


def _job_to_row_params(job: JobPosting) -> dict[str, Any]:
    return {
        "job_hash": job.job_hash,
        "company": job.company,
        "title": job.title,
        "url": job.url,
        "source": job.source,
        "location": job.location,
        "employment_type": job.employment_type,
        "department": job.department,
        "industry_category": job.industry_category,
        "role_category": job.role_category,
        "description": job.description,
        "qualifications": job.qualifications,
        "preferred_qualifications": job.preferred_qualifications,
        "required_skills": json.dumps(job.required_skills),
        "posted_date": job.posted_date,
        "application_deadline": job.application_deadline,
        "date_found": job.date_found,
        "last_checked": job.last_checked,
        "fit_score": job.fit_score,
        "score_role_fit": job.score_role_fit,
        "score_industry_fit": job.score_industry_fit,
        "score_eligibility_fit": job.score_eligibility_fit,
        "score_skills_fit": job.score_skills_fit,
        "score_location_fit": job.score_location_fit,
        "score_explanation": job.score_explanation,
        "is_flagged": int(job.is_flagged),
        "flag_reasons": json.dumps(job.flag_reasons),
        "status": job.status,
        "notes": job.notes,
        "is_active": int(job.is_active),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def upsert_job(conn: sqlite3.Connection, job: JobPosting) -> tuple[int, bool]:
    """Insert a new job, or update an existing one matched by job_hash.

    Returns (row_id, was_new).
    """
    existing = conn.execute(
        "SELECT id FROM jobs WHERE job_hash = ?", (job.job_hash,)
    ).fetchone()

    params = _job_to_row_params(job)

    if existing is None:
        columns = list(params.keys())
        placeholders = ", ".join(f":{c}" for c in columns)
        conn.execute(
            f"INSERT INTO jobs ({', '.join(columns)}) VALUES ({placeholders})",
            params,
        )
        row_id = conn.execute(
            "SELECT id FROM jobs WHERE job_hash = ?", (job.job_hash,)
        ).fetchone()["id"]
        return row_id, True

    row_id = existing["id"]
    set_clause = ", ".join(f"{field} = :{field}" for field in _REFRESHABLE_FIELDS)
    params["id"] = row_id
    conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = :id", params)
    return row_id, False


def bulk_upsert(jobs: list[JobPosting]) -> dict[str, int]:
    """Upsert many jobs in a single transaction. Used at the end of each
    collection cycle.
    """
    new_count = 0
    updated_count = 0
    with db_transaction() as conn:
        for job in jobs:
            _, was_new = upsert_job(conn, job)
            if was_new:
                new_count += 1
            else:
                updated_count += 1
    logger.info("Saved %d jobs (%d new, %d updated)", len(jobs), new_count, updated_count)
    return {"new": new_count, "updated": updated_count, "total_seen": len(jobs)}


def mark_stale_jobs_for_company(company: str, seen_hashes: set[str]) -> int:
    """After fully collecting a company's postings, mark any previously
    stored posting for that company that was NOT seen this run as
    inactive (likely removed/filled). Returns the number of rows changed.

    Skipped if seen_hashes is empty, so a source that failed mid-collection
    doesn't wipe out everything we know about that company.
    """
    if not seen_hashes:
        return 0
    with db_transaction() as conn:
        placeholders = ", ".join("?" for _ in seen_hashes)
        cursor = conn.execute(
            f"""
            UPDATE jobs SET is_active = 0, updated_at = ?
            WHERE company = ? AND is_active = 1 AND job_hash NOT IN ({placeholders})
            """,
            [utc_now_iso(), company, *seen_hashes],
        )
        return cursor.rowcount


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["required_skills"] = json.loads(d.get("required_skills") or "[]")
    d["flag_reasons"] = json.loads(d.get("flag_reasons") or "[]")
    d["score_explanation"] = json.loads(d.get("score_explanation") or "{}")
    d["is_flagged"] = bool(d["is_flagged"])
    d["is_active"] = bool(d["is_active"])
    return d


def get_all_jobs() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM jobs ORDER BY fit_score DESC").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_job_by_id(job_id: int) -> Optional[dict[str, Any]]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_job_status(job_id: int, status: str) -> None:
    with db_transaction() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now_iso(), job_id),
        )


def update_job_notes(job_id: int, notes: str) -> None:
    with db_transaction() as conn:
        conn.execute(
            "UPDATE jobs SET notes = ?, updated_at = ? WHERE id = ?",
            (notes, utc_now_iso(), job_id),
        )


def record_collection_run(
    started_at: str,
    finished_at: str,
    sources_attempted: int,
    sources_succeeded: int,
    sources_failed: int,
    jobs_seen: int,
    jobs_new: int,
    jobs_updated: int,
    notes: str = "",
) -> None:
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO collection_runs
                (started_at, finished_at, sources_attempted, sources_succeeded,
                 sources_failed, jobs_seen, jobs_new, jobs_updated, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at, finished_at, sources_attempted, sources_succeeded,
                sources_failed, jobs_seen, jobs_new, jobs_updated, notes,
            ),
        )


def get_recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM collection_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_to_csv(output_path: Path) -> int:
    """Write every job to a CSV file. Returns the number of rows written."""
    jobs = get_all_jobs()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not jobs:
        logger.warning("No jobs to export.")
        return 0

    fieldnames = list(jobs[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            row = dict(job)
            row["required_skills"] = ", ".join(row["required_skills"])
            row["flag_reasons"] = ", ".join(row["flag_reasons"])
            row["score_explanation"] = json.dumps(row["score_explanation"])
            writer.writerow(row)

    logger.info("Exported %d jobs to %s", len(jobs), output_path)
    return len(jobs)
