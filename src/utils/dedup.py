"""
Deduplication helpers.

The same posting can show up more than once within a single collection run
(e.g. a company lists it under two departments) and will definitely show up
across runs (we re-check the same boards every cycle). We need a stable
identity for a posting that does NOT change just because a field like
`last_checked` was updated.
"""
from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import JobPosting


def _normalize(value: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation-heavy noise so
    trivial formatting differences (extra spaces, mixed case) don't create
    duplicate hashes for what is clearly the same posting.
    """
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    return value


def compute_job_hash(company: str, title: str, location: str, url: str) -> str:
    """A stable identity for a job posting.

    We prefer the posting URL as the strongest signal (it usually encodes a
    unique job requisition ID), combined with company/title/location so
    that if a URL ever gets reused or truncated we still don't accidentally
    merge two unrelated postings.
    """
    key_parts = [
        _normalize(company),
        _normalize(title),
        _normalize(location),
        _normalize(url),
    ]
    key = "|".join(key_parts)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def dedupe_jobs(jobs: list["JobPosting"]) -> list["JobPosting"]:
    """Drop duplicate postings (same job_hash) within a batch, keeping the
    first occurrence. Cross-run/cross-cycle deduplication is handled
    separately by the database upsert in src/database/repository.py - this
    only protects against duplicates appearing within one collection pass
    (e.g. a posting listed under two departments on the same board).
    """
    seen: set[str] = set()
    unique: list["JobPosting"] = []
    for job in jobs:
        if job.job_hash in seen:
            continue
        seen.add(job.job_hash)
        unique.append(job)
    return unique
