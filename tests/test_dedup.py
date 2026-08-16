"""Tests for src/utils/dedup.py."""
from __future__ import annotations

from src.database.models import JobPosting
from src.utils.dedup import compute_job_hash, dedupe_jobs


def test_compute_job_hash_is_stable_for_identical_input():
    h1 = compute_job_hash("Acme", "Mechanical Engineer Intern", "Columbus, OH", "https://acme.com/1")
    h2 = compute_job_hash("Acme", "Mechanical Engineer Intern", "Columbus, OH", "https://acme.com/1")
    assert h1 == h2


def test_compute_job_hash_ignores_case_and_whitespace_differences():
    h1 = compute_job_hash("Acme", "Mechanical Engineer Intern", "Columbus, OH", "https://acme.com/1")
    h2 = compute_job_hash("  acme  ", "mechanical   engineer intern", "columbus, oh", "https://acme.com/1")
    assert h1 == h2


def test_compute_job_hash_differs_for_different_jobs():
    h1 = compute_job_hash("Acme", "Mechanical Engineer Intern", "Columbus, OH", "https://acme.com/1")
    h2 = compute_job_hash("Acme", "Manufacturing Engineer Intern", "Columbus, OH", "https://acme.com/2")
    assert h1 != h2


def test_dedupe_jobs_removes_duplicates_keeping_first():
    job_a = JobPosting(company="Acme", title="A", url="u1", source="greenhouse", job_hash="same", fit_score=10)
    job_b = JobPosting(company="Acme", title="B", url="u2", source="greenhouse", job_hash="same", fit_score=99)
    job_c = JobPosting(company="Acme", title="C", url="u3", source="greenhouse", job_hash="different")

    result = dedupe_jobs([job_a, job_b, job_c])

    assert len(result) == 2
    assert result[0].title == "A"  # first occurrence wins
    assert result[1].title == "C"


def test_dedupe_jobs_handles_empty_list():
    assert dedupe_jobs([]) == []
