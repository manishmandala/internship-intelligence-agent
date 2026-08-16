# Internship Intelligence Agent

A personal tool that collects mechanical/design/manufacturing engineering,
product & program management, technical/management consulting, and
robotics/AI internship & co-op postings from public company career APIs,
scores each one for fit against a specific candidate profile, and presents
everything in a local Streamlit dashboard.

Built for an Ohio State University Mechanical Engineering student
(class of 2029), open to roles anywhere in the United States.

## What this actually does (and doesn't)

- Polls a set of **public, structured, unauthenticated JSON APIs** that
  career sites themselves use to render their job listings: Greenhouse's
  board API, Lever's postings API, Ashby's posting API, Workday's CXS
  search API (the same one Workday-hosted career sites like
  jobs.boeing.com call client-side), and Amazon's own `amazon.jobs` search
  API. It does **not** scrape rendered HTML, bypass logins/CAPTCHAs, or
  ignore rate limits.
- 14 of the 43 companies on the "wish list" expose one of these APIs today
  (see [Limitations](#limitations)). Everyone else uses SuccessFactors,
  iCIMS, Phenom, or a bespoke portal with no discoverable public JSON
  endpoint - those are recorded as `unsupported` and skipped, not faked.
- Scores are a **rule-based heuristic** (weighted keyword matching +
  eligibility/location logic), not a machine-learned or LLM judgment. It's
  a starting point for triage, not a guarantee of relevance.

## Architecture

```
internship-intelligence-agent/
  config/               Candidate profile, keywords/skills vocab, company list
  data/                 SQLite DB + CSV export live here (gitignored)
  logs/                 Rotating log files from every run (gitignored)
  src/
    collectors/         One class per source (Greenhouse, Lever, Ashby, Workday, Amazon, ...)
    parsers/             Raw source JSON -> normalized JobPosting
    scoring/             Rule-based fit scorer (+ location/eligibility logic)
    analysis/            Skill extraction, summary statistics
    database/            SQLite schema, connection handling, all SQL (repository.py)
    utils/               Shared HTTP client (retries/backoff/rate-limit), logging, dedup
    main.py              CLI entry point / orchestrator
  dashboard/
    app.py               Streamlit dashboard
  tests/                 pytest suite
```

**Data flow for one collection cycle:**
`main.py` -> for each configured company, its `Collector.collect()` hits
that source's API -> each raw job dict is normalized into a `JobPosting`
by `parsers/job_parser.py` (HTML cleaned, role/industry classified, skills
extracted) -> `RuleBasedScorer` scores it -> duplicates within the batch
are dropped by hash -> everything is upserted into SQLite (existing
postings get refreshed, your status/notes are preserved) -> a text summary
is printed and logged.

### Why it's built this way

- **Collectors implement one interface** (`src/collectors/base.py`):
  `collect(session) -> CollectionResult`. Adding a new Greenhouse or Lever
  company is a one-line addition to `config/companies.py` - no new code.
  Adding a genuinely new source (like Amazon's search API) means writing
  one small collector class and registering it in
  `src/collectors/registry.py`.
- **Scoring is behind an interface too** (`src/scoring/scorer.py`,
  `BaseScorer`). `RuleBasedScorer` is the only implementation today; a
  future LLM-backed scorer can implement the same `score()` method and be
  swapped in in `src/main.py` without touching anything else.
- **All SQL lives in `src/database/repository.py`.** Nothing else touches
  the `jobs` table directly, so the dedup/upsert logic can't accidentally
  be bypassed somewhere else in the codebase.

## Installation (Windows PowerShell)

```powershell
cd internship-intelligence-agent

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Optional: copy the environment template if you want to change defaults
# (request delay, log directory, etc.) - none of this is required to run.
copy .env.example .env
```

If PowerShell blocks the activation script, run this once as yourself
(not admin) and try again: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Running a collection

From the project root, with the virtual environment activated:

```powershell
# One collection cycle across every supported company (a few minutes -
# the Workday-backed companies each need one search request plus one
# detail request per matched posting)
python -m src.main

# Also write data\internships.csv after each cycle
python -m src.main --export-csv

# Restrict to specific companies (useful for testing)
python -m src.main --companies "SpaceX,Lucid,Anduril"

# Run 5 cycles, 30 minutes apart (default wait is 30m)
python -m src.main --cycles 5 --wait 30m

# Leave it running for ~3 hours, polling sources on a fixed cadence
python -m src.main --duration 3h --wait 45m
```

Every run: initializes the database if needed, runs each configured
collector, parses/dedupes/scores/saves results, and prints a summary. A
failing source is logged and skipped - it never stops the rest of the run.
Detailed logs are written to `logs\internship_agent.log` (rotated at 5MB,
5 backups kept).

## Running the dashboard

In a **second** terminal (leave a collection running in the first one if
you want, the dashboard reads the same SQLite file safely via WAL mode):

```powershell
cd internship-intelligence-agent
.\.venv\Scripts\Activate.ps1
streamlit run dashboard\app.py
```

This opens a browser tab at `http://localhost:8501`. From there you can:
sort/filter by company, industry, role category, location, internship vs.
co-op, minimum fit score, or free-text keyword search; click straight
through to the application URL; edit a posting's **status**
(new/interested/applied/interviewing/rejected/offer/ignored) and **notes**
inline in the table and click "Save changes"; and view an **Insights** tab
with highest-fit opportunities, newly discovered postings, deadlines
coming up, top companies, and top skills (overall and within high-fit
roles specifically).

## Adding another company or source

**If the company uses Greenhouse or Lever:** find their board token (it's
in the URL of their public careers page, e.g.
`boards.greenhouse.io/<token>` or `jobs.lever.co/<company>`), verify it
resolves - `curl https://boards-api.greenhouse.io/v1/boards/<token>/jobs`
or `curl https://api.lever.co/v0/postings/<company>?mode=json` - and add
one line to `config/companies.py`:

```python
CompanySource("New Co", "aerospace_defense", "greenhouse", "newco-token"),
```

That's it - `src/collectors/registry.py` will pick it up automatically.

**If the company uses Ashby:** same idea - find the board name from the
`jobs.ashbyhq.com/<name>` link on their careers page (or grep their
careers page HTML for `ashbyhq.com`), verify with
`curl https://api.ashbyhq.com/posting-api/job-board/<name>`, and add:

```python
CompanySource("New Co", "robotics_automation", "ashby", "newco-board-name"),
```

**If the company uses Workday:** load their real public careers page and
search the HTML for a `myworkdayjobs.com` URL (e.g.
`curl -sL https://company.com/careers | grep -oE "[a-z0-9.-]*\.wd[0-9]+\.myworkdayjobs\.com/[a-zA-Z0-9_/-]*"`).
That gives you `<tenant>.<wdHost>.myworkdayjobs.com/<site>` - verify it
with a POST to `https://<tenant>.<wdHost>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs`
(body: `{"appliedFacets":{},"limit":5,"offset":0,"searchText":"intern"}`),
then add:

```python
CompanySource("New Co", "medical_devices", "workday", "tenant/wdHost/site"),
```

**If the company uses something else entirely:** write a new collector class in
`src/collectors/`, subclassing `BaseCollector` and implementing
`collect(session)` to return a `CollectionResult`. Use
`src/parsers/job_parser.py`'s `build_job_posting()` to turn raw fields into
a `JobPosting` (it handles HTML cleaning, role/industry classification,
and skill extraction for you - see `src/collectors/amazon.py` for a
complete example). Register the new `ats` string in
`src/collectors/registry.py`'s `_COLLECTOR_CLASSES` dict, then set that
company's `ats` field in `config/companies.py`.

## Database structure

SQLite at `data\internships.db` (gitignored - it's local, generated data).
Two tables, defined in `src/database/schema.sql`:

- **`jobs`** - one row per unique posting. Uniqueness is enforced by
  `job_hash`, a sha256 of the normalized `(company, title, location, url)`
  tuple (`src/utils/dedup.py`). Re-collecting the same posting **updates**
  its row (`src/database/repository.py::upsert_job`) rather than inserting
  a duplicate - source-derived fields (title, description, score, etc.)
  are refreshed, but your `status` and `notes` are never touched by a
  re-collection. A posting no longer seen on a company's board during a
  full collection of that company is marked `is_active = 0` rather than
  deleted, so you can see what disappeared.
- **`collection_runs`** - one row per `run_collection_cycle()` call, for
  the dashboard's "recent runs" panel and for debugging a multi-hour run
  after the fact.

Export to CSV any time with `python -m src.main --export-csv`, or from
Python: `python -c "from src.database import repository; from pathlib import Path; repository.export_to_csv(Path('data/internships.csv'))"`.

## Scoring methodology

Every posting gets five 0-100 sub-scores (`src/scoring/scorer.py`,
weights in `src/scoring/rules.py`), combined into one weighted `fit_score`:

| Sub-score | Weight | How it's computed |
|---|---|---|
| Role fit | 30% | Keyword match against the posting's **title first**, falling back to the description body only if the title has no signal (and requiring 2+ body hits to avoid one incidental mention deciding the category) - see `src/parsers/classifiers.py`. Categories: mechanical/design, manufacturing, robotics/AI/hardware, product/program management, consulting/strategy, other. |
| Industry fit | 20% | Comes directly from the company's configured industry in `config/companies.py` (more reliable than guessing from text for a company-specific job board). |
| Eligibility fit | 15% | Scans qualifications text for explicit graduation years (e.g. "graduating in 2027-2028") and compares to the candidate's class year; no explicit requirement found is treated as neutral, not penalized. |
| Skills fit | 15% | Fraction of extracted skills that are in a "high-value for this profile" set (SolidWorks, CAD, FEA, ANSYS, ROS, etc. - `config/keywords.py`). |
| Location fit | 20% | Classifies the posting's location string as US / non-US / unknown (`src/scoring/location.py`); non-US scores 0 since the candidate is US-only. |

A posting is also **flagged** as noteworthy if: its fit score is 85+, its
text contains selective-program language ("highly selective", "rotational
program", etc.), or it has a known application deadline within 14 days.

This is deliberately keyword-based so it runs with **no API key and no
cost**. `src/scoring/scorer.py` defines a `BaseScorer` interface
specifically so an LLM-backed scorer can be added later as a second
implementation without changing anything else in the pipeline.

## Skills tracked

`config/keywords.py::SKILL_VOCABULARY` - Python, MATLAB, SolidWorks, Creo,
CATIA, CAD, GD&T, FEA, ANSYS, Manufacturing, CNC, Robotics, ROS, C, C++,
SQL, Excel, Data Analysis, Project Management, Communication, AutoCAD, NX,
Fusion 360, 3D Printing, Six Sigma, PLC, LabVIEW, R, Java, and more.
Extraction (`src/analysis/skills.py`) uses word-boundary regex matching;
single-letter languages (`C`, `R`) use narrower phrase-based patterns
specifically because a naive `\bC\b` match fires on things like
`"8 U.S.C. 1101"` or `"our R&D team"` in real job postings' boilerplate -
this was caught and fixed during development (see `tests/test_parsers.py`
for the regression tests).

## Limitations

- **14 of 43 requested companies are actually collectible today**: Boeing,
  SpaceX, Blue Origin, Lucid, Amazon, Rockwell Automation, Stryker, Abbott,
  Johnson & Johnson, BCG, Accenture, Boston Dynamics, Anduril, and Applied
  Intuition. The other 29 (Lockheed, Tesla, Apple, McKinsey, Medtronic,
  Caterpillar, etc.) use SuccessFactors, iCIMS, Phenom, or a bespoke portal
  with no discoverable public JSON API, or are a JS-rendered career site
  where a Workday tenant may exist but wasn't identifiable via a simple
  unauthenticated fetch - see `config/companies.py` for the full list with
  per-company notes. Run `python -m src.main` and check the summary's
  "Unsupported sources" line for the current list. Some of these (e.g.
  Lockheed Martin, Honeywell, Caterpillar) likely *do* run on Workday and
  could be added the same way Boeing was - see "Adding another company or
  source" above - they just weren't confirmed during this build.
- **Scoring is a heuristic**, not ground truth. It's meant to help you
  triage a larger list faster, not to replace reading the actual posting.
- **Greenhouse/Lever/Ashby boards list every open role globally**, not
  just internships - the collector filters by title (word-boundary match
  on "intern"/"co-op"), so a company that titles its internships unusually
  could be missed.
- **Workday's search is full-text, not title-only** - searching "intern"
  can return hundreds of results where the word only appears in the body
  (e.g. "you may have started as an intern..."), most of which won't pass
  the title filter. This collector searches up to 60 ranked results per
  company and fetches full detail only for title matches (capped at 30
  detail requests per company per run), so a company with internships
  ranked outside the top 60 full-text results could be missed. It's also
  the slowest collector - each matched posting needs its own detail
  request, so a company with 20-30 real internship openings can take
  30-50 seconds to fully collect.
- **Application deadlines** are well-populated by Workday (`endDate`),
  sometimes present on Greenhouse, and not exposed at all by Lever, Ashby,
  or Amazon's search API. Expect deadlines on Workday-sourced postings and
  gaps elsewhere.
- Amazon's search API returns a limited result window per query and is
  queried once per keyword in `config/keywords.py::SEARCH_KEYWORDS` -
  it won't necessarily surface every open Amazon internship.

## Ethical scraping practices

- Every request carries a descriptive `User-Agent` identifying this as a
  personal internship-search tool with a contact email
  (`src/utils/http.py`, configured via `IIA_CONTACT_EMAIL` in `.env`).
- Only public, unauthenticated, structured JSON endpoints are used - the
  same ones each career site's own search page calls. No HTML scraping,
  no login bypass, no CAPTCHA solving, no header spoofing to evade
  detection.
- A per-host politeness delay (`IIA_REQUEST_DELAY_SECONDS`, default 1.5s)
  is enforced between requests, plus request timeouts and bounded retries
  with exponential backoff (`src/utils/http.py`) - this project will never
  hammer a career site.
- A company with no reliable public API is left `unsupported` rather than
  worked around.

## Testing

```powershell
pytest
# or, more verbosely:
pytest -v
```

67 tests cover: title/internship filtering (including regression tests for
"Internal" ≠ "Intern"), role/industry classification, skill extraction
(including the C/R false-positive fixes), HTML cleaning, job-hash dedup
logic, the rule-based scorer's sub-scores and flags, the database upsert
behavior (new vs. updated rows, and that re-collection never clobbers your
status/notes), Workday's relative-date parsing, and a config sanity check
that no company appears twice in `config/companies.py` (a real bug caught
during development - see `tests/test_companies_config.py`).

## Long-running / unattended use

`python -m src.main --duration 3h --wait 45m` will run indefinitely for
about 3 hours, collecting every 45 minutes, logging everything to
`logs\internship_agent.log`, and continuing past any individual source
failure. Stop it early any time with Ctrl+C - whatever was already saved
to the database stays saved.
