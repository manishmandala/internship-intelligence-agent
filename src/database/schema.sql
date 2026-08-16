-- Internship Intelligence Agent - SQLite schema
--
-- `jobs.job_hash` is the dedup key: a sha256 of normalized
-- (company, title, location, url). Re-running a collection cycle
-- upserts on this key instead of inserting duplicate rows - see
-- src/database/repository.py `upsert_job`.

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_hash TEXT NOT NULL UNIQUE,

    -- Identity / source
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,

    -- Core fields
    location TEXT NOT NULL DEFAULT 'Unknown',
    employment_type TEXT NOT NULL DEFAULT 'Unknown',
    department TEXT NOT NULL DEFAULT '',
    industry_category TEXT NOT NULL DEFAULT 'other',
    role_category TEXT NOT NULL DEFAULT 'other',

    -- Content
    description TEXT NOT NULL DEFAULT '',
    qualifications TEXT NOT NULL DEFAULT '',
    preferred_qualifications TEXT NOT NULL DEFAULT '',
    required_skills TEXT NOT NULL DEFAULT '[]',  -- JSON list

    -- Dates
    posted_date TEXT,
    application_deadline TEXT,
    date_found TEXT NOT NULL,
    last_checked TEXT NOT NULL,

    -- Scoring
    fit_score INTEGER NOT NULL DEFAULT 0,
    score_role_fit INTEGER NOT NULL DEFAULT 0,
    score_industry_fit INTEGER NOT NULL DEFAULT 0,
    score_eligibility_fit INTEGER NOT NULL DEFAULT 0,
    score_skills_fit INTEGER NOT NULL DEFAULT 0,
    score_location_fit INTEGER NOT NULL DEFAULT 0,
    score_explanation TEXT NOT NULL DEFAULT '{}',  -- JSON dict

    -- Flags
    is_flagged INTEGER NOT NULL DEFAULT 0,
    flag_reasons TEXT NOT NULL DEFAULT '[]',  -- JSON list

    -- User workflow state
    status TEXT NOT NULL DEFAULT 'new',
    notes TEXT NOT NULL DEFAULT '',

    -- Bookkeeping
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_fit_score ON jobs(fit_score);
CREATE INDEX IF NOT EXISTS idx_jobs_industry ON jobs(industry_category);
CREATE INDEX IF NOT EXISTS idx_jobs_role ON jobs(role_category);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_date_found ON jobs(date_found);

-- One row per collection run, for the dashboard's "last run" summary and
-- for `python -m src.main` to report cumulative stats across cycles.
CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    sources_attempted INTEGER NOT NULL DEFAULT 0,
    sources_succeeded INTEGER NOT NULL DEFAULT 0,
    sources_failed INTEGER NOT NULL DEFAULT 0,
    jobs_seen INTEGER NOT NULL DEFAULT 0,
    jobs_new INTEGER NOT NULL DEFAULT 0,
    jobs_updated INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT ''
);
