"""
Tests for src/database/repository.py - specifically the upsert-based
dedup behavior, which is the part of the project most likely to silently
break (e.g. accidentally overwriting a user's status/notes on re-collect).
"""
from __future__ import annotations

from src.database import repository
from src.database.db import get_connection
from src.database.models import JobPosting


def make_job(**overrides) -> JobPosting:
    defaults = dict(
        company="TestCo",
        title="Mechanical Engineering Intern",
        url="https://example.com/jobs/123",
        source="greenhouse",
        job_hash="abc123",
        location="Columbus, OH",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def test_upsert_job_inserts_new_job(temp_db):
    conn = get_connection()
    job = make_job()
    row_id, was_new = repository.upsert_job(conn, job)
    conn.commit()
    conn.close()

    assert was_new is True
    assert row_id is not None

    stored = repository.get_job_by_id(row_id)
    assert stored["company"] == "TestCo"
    assert stored["title"] == "Mechanical Engineering Intern"
    assert stored["status"] == "new"


def test_upsert_job_updates_existing_job_by_hash(temp_db):
    conn = get_connection()
    job_v1 = make_job(title="Mechanical Engineering Intern", fit_score=50)
    row_id_1, was_new_1 = repository.upsert_job(conn, job_v1)
    conn.commit()

    # Same job_hash (same company/title/location/url) seen again, e.g. on
    # the next collection cycle, but with an updated fit_score.
    job_v2 = make_job(title="Mechanical Engineering Intern", fit_score=75)
    row_id_2, was_new_2 = repository.upsert_job(conn, job_v2)
    conn.commit()
    conn.close()

    assert was_new_2 is False
    assert row_id_1 == row_id_2

    all_jobs = repository.get_all_jobs()
    assert len(all_jobs) == 1
    assert all_jobs[0]["fit_score"] == 75


def test_upsert_preserves_user_status_and_notes_on_recollection(temp_db):
    conn = get_connection()
    job = make_job()
    row_id, _ = repository.upsert_job(conn, job)
    conn.commit()
    conn.close()

    # Simulate the user interacting with the posting via the dashboard.
    repository.update_job_status(row_id, "applied")
    repository.update_job_notes(row_id, "Talked to a recruiter at career fair")

    # Re-collection sees the same posting again (same hash) with refreshed
    # source fields, but should NOT clobber status/notes.
    conn = get_connection()
    job_recollected = make_job(fit_score=99, description="Updated description")
    repository.upsert_job(conn, job_recollected)
    conn.commit()
    conn.close()

    stored = repository.get_job_by_id(row_id)
    assert stored["status"] == "applied"
    assert stored["notes"] == "Talked to a recruiter at career fair"
    assert stored["fit_score"] == 99  # source fields DO refresh
    assert stored["description"] == "Updated description"


def test_bulk_upsert_counts_new_and_updated(temp_db):
    job1 = make_job(job_hash="hash-1", title="Job One")
    job2 = make_job(job_hash="hash-2", title="Job Two")
    stats = repository.bulk_upsert([job1, job2])
    assert stats == {"new": 2, "updated": 0, "total_seen": 2}

    # Re-run with one repeated hash and one new hash.
    job2_updated = make_job(job_hash="hash-2", title="Job Two", fit_score=88)
    job3 = make_job(job_hash="hash-3", title="Job Three")
    stats2 = repository.bulk_upsert([job2_updated, job3])
    assert stats2 == {"new": 1, "updated": 1, "total_seen": 2}

    assert len(repository.get_all_jobs()) == 3


def test_mark_stale_jobs_for_company_deactivates_missing_postings(temp_db):
    job1 = make_job(job_hash="hash-1", title="Job One", company="Acme")
    job2 = make_job(job_hash="hash-2", title="Job Two", company="Acme")
    repository.bulk_upsert([job1, job2])

    # This collection cycle only saw job1 - job2 must have been removed
    # from Acme's board.
    changed = repository.mark_stale_jobs_for_company("Acme", {"hash-1"})
    assert changed == 1

    all_jobs = {j["job_hash"]: j for j in repository.get_all_jobs()}
    assert all_jobs["hash-1"]["is_active"] is True
    assert all_jobs["hash-2"]["is_active"] is False


def test_mark_stale_jobs_skips_when_seen_hashes_empty(temp_db):
    job1 = make_job(job_hash="hash-1", title="Job One", company="Acme")
    repository.bulk_upsert([job1])

    # An empty seen_hashes set means the collector likely failed before
    # producing any jobs - we must not wipe out everything we know.
    changed = repository.mark_stale_jobs_for_company("Acme", set())
    assert changed == 0
    assert repository.get_all_jobs()[0]["is_active"] is True
