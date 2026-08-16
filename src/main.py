"""
Entry point for the Internship Intelligence Agent.

Usage (from the project root, with the virtual environment activated):

    python -m src.main                          # one collection cycle
    python -m src.main --cycles 5 --wait 30m     # 5 cycles, 30 min apart
    python -m src.main --duration 3h             # run repeatedly for ~3 hours
    python -m src.main --companies SpaceX,Lucid  # restrict to specific companies
    python -m src.main --export-csv              # also write data/internships.csv

Each cycle: initialize the DB -> run every configured collector -> parse
-> dedupe -> score -> save -> print a summary. A failing source is logged
and skipped; it never stops the rest of the run.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.companies import COMPANIES, active_companies, unsupported_companies
from config.settings import DATA_DIR
from src.analysis.stats import summary_report
from src.collectors.registry import build_collectors
from src.database import repository
from src.database.db import initialize_database
from src.database.models import JobPosting
from src.scoring.scorer import RuleBasedScorer
from src.utils.dedup import dedupe_jobs
from src.utils.http import RateLimitedSession
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_DURATION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([hms])$", re.IGNORECASE)


def parse_duration(text: str) -> timedelta:
    """Parse a duration string like '3h', '90m', '45s' into a timedelta."""
    match = _DURATION_PATTERN.match(text.strip())
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid duration '{text}'. Use a number followed by h, m, or s (e.g. 3h, 90m, 45s)."
        )
    amount, unit = float(match.group(1)), match.group(2).lower()
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    return timedelta(seconds=amount)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect, score, and store internship/co-op postings."
    )
    parser.add_argument(
        "--cycles", type=int, default=1,
        help="Number of collection cycles to run (default: 1). Ignored if --duration is set.",
    )
    parser.add_argument(
        "--wait", type=str, default="30m",
        help="Wait time between cycles, e.g. '30m', '1h', '90s' (default: 30m).",
    )
    parser.add_argument(
        "--duration", type=str, default=None,
        help="Run repeated cycles for approximately this long, e.g. '3h'. "
             "Overrides --cycles.",
    )
    parser.add_argument(
        "--companies", type=str, default=None,
        help="Comma-separated company names to restrict this run to (default: all supported).",
    )
    parser.add_argument(
        "--export-csv", action="store_true",
        help="Export all stored jobs to data/internships.csv after each cycle.",
    )
    return parser.parse_args(argv)


def _select_companies(companies_arg: str | None) -> list:
    if not companies_arg:
        return active_companies()

    requested = {name.strip().lower() for name in companies_arg.split(",")}
    selected = [c for c in COMPANIES if c.name.lower() in requested]
    unknown = requested - {c.name.lower() for c in selected}
    if unknown:
        logger.warning("Unknown company name(s) ignored: %s", ", ".join(sorted(unknown)))
    unsupported = [c for c in selected if c.ats == "unsupported"]
    for c in unsupported:
        logger.warning("'%s' has no supported collector (%s); skipping.", c.name, c.notes)
    return [c for c in selected if c.ats != "unsupported"]


def run_collection_cycle(companies: list | None = None) -> dict:
    """Run exactly one collect -> parse -> dedupe -> score -> save pass.

    Returns a dict of stats about what happened, and also persists a row
    to the `collection_runs` table.
    """
    started_at = datetime.now(timezone.utc)
    logger.info("=" * 70)
    logger.info("Starting collection cycle at %s", started_at.isoformat(timespec="seconds"))

    collectors = build_collectors(companies)
    session = RateLimitedSession()
    scorer = RuleBasedScorer()

    all_jobs: list[JobPosting] = []
    sources_succeeded = 0
    sources_failed = 0
    failures: list[tuple[str, str]] = []

    for collector in collectors:
        company_name = collector.company.name
        logger.info("Collecting: %s (%s)", company_name, collector.company.ats)
        try:
            result = collector.collect(session)
        except Exception as exc:
            # A collector's collect() should already catch its own errors
            # and return a failed CollectionResult - this is a last-resort
            # safety net so a genuinely unexpected bug in one collector
            # still can't kill the whole run.
            logger.exception("Unhandled exception collecting %s", company_name)
            sources_failed += 1
            failures.append((company_name, str(exc)))
            continue

        if not result.success:
            sources_failed += 1
            failures.append((company_name, result.error))
            logger.warning("Source failed: %s - %s", company_name, result.error)
            continue

        sources_succeeded += 1
        unique_jobs = dedupe_jobs(result.jobs)
        for job in unique_jobs:
            scorer.score(job)
        all_jobs.extend(unique_jobs)

        # Mark postings we didn't see this run as inactive, so the
        # dashboard can distinguish "still open" from "no longer listed".
        seen_hashes = {job.job_hash for job in unique_jobs}
        repository.mark_stale_jobs_for_company(company_name, seen_hashes)

    all_jobs = dedupe_jobs(all_jobs)
    save_stats = repository.bulk_upsert(all_jobs) if all_jobs else {"new": 0, "updated": 0, "total_seen": 0}

    finished_at = datetime.now(timezone.utc)
    repository.record_collection_run(
        started_at=started_at.isoformat(timespec="seconds"),
        finished_at=finished_at.isoformat(timespec="seconds"),
        sources_attempted=len(collectors),
        sources_succeeded=sources_succeeded,
        sources_failed=sources_failed,
        jobs_seen=save_stats["total_seen"],
        jobs_new=save_stats["new"],
        jobs_updated=save_stats["updated"],
        notes="; ".join(f"{name}: {err}" for name, err in failures) if failures else "",
    )

    duration = (finished_at - started_at).total_seconds()
    logger.info(
        "Cycle complete in %.1fs - sources: %d ok / %d failed - jobs: %d new / %d updated",
        duration, sources_succeeded, sources_failed, save_stats["new"], save_stats["updated"],
    )
    if failures:
        for name, err in failures:
            logger.info("  failed source: %s -> %s", name, err)

    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "sources_attempted": len(collectors),
        "sources_succeeded": sources_succeeded,
        "sources_failed": sources_failed,
        "failures": failures,
        **save_stats,
    }


def print_run_summary() -> None:
    jobs = repository.get_all_jobs()
    report = summary_report(jobs)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total jobs in database : {report['total_jobs']}")
    print(f"Currently active       : {report['active_jobs']}")
    print(f"Flagged as noteworthy  : {report['flagged_jobs']}")
    print(f"Average fit score      : {report['average_fit_score']}")

    print("\nTop companies by posting count:")
    for name, count in report["top_companies"]:
        print(f"  {name:<25} {count}")

    print("\nMost common skills across postings:")
    for skill, count in report["top_skills"]:
        print(f"  {skill:<25} {count}")

    print("\nHighest-fit opportunities:")
    for company, title, score in report["highest_fit"]:
        print(f"  [{score:>3}] {company} - {title}")

    supported = active_companies()
    unsupported = unsupported_companies()
    print(f"\nSupported sources ({len(supported)}): " + ", ".join(c.name for c in supported))
    print(f"Unsupported sources ({len(unsupported)}, no reliable public API found): "
          + ", ".join(c.name for c in unsupported))
    print("=" * 70 + "\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logger.info("Initializing database...")
    initialize_database()

    companies = _select_companies(args.companies)
    if not companies:
        logger.error("No supported companies to collect from. Exiting.")
        return 1

    if args.duration:
        run_for = parse_duration(args.duration)
        wait_between = parse_duration(args.wait)
        deadline = datetime.now(timezone.utc) + run_for
        cycle_num = 0
        while datetime.now(timezone.utc) < deadline:
            cycle_num += 1
            logger.info("--- Cycle %d (duration mode, ends %s) ---", cycle_num, deadline.isoformat(timespec="minutes"))
            run_collection_cycle(companies)
            if args.export_csv:
                repository.export_to_csv(DATA_DIR / "internships.csv")
            if datetime.now(timezone.utc) >= deadline:
                break
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            sleep_for = min(wait_between.total_seconds(), max(remaining, 0))
            if sleep_for > 0:
                logger.info("Waiting %.0f seconds before next cycle...", sleep_for)
                time.sleep(sleep_for)
    else:
        wait_between = parse_duration(args.wait)
        for cycle_num in range(1, args.cycles + 1):
            logger.info("--- Cycle %d of %d ---", cycle_num, args.cycles)
            run_collection_cycle(companies)
            if args.export_csv:
                repository.export_to_csv(DATA_DIR / "internships.csv")
            if cycle_num < args.cycles:
                logger.info("Waiting %.0f seconds before next cycle...", wait_between.total_seconds())
                time.sleep(wait_between.total_seconds())

    print_run_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
