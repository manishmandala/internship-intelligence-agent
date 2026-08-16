"""
Starter company list for the Internship Intelligence Agent.

Each entry describes how (if at all) a company's postings can be reached
through a reliable, publicly accessible, structured source:

- "greenhouse": the company publishes an open Greenhouse job board API at
  https://boards-api.greenhouse.io/v1/boards/<ats_id>/jobs
- "lever": the company publishes an open Lever postings API at
  https://api.lever.co/v0/postings/<ats_id>
- "amazon_jobs_api": Amazon's own public JSON search API used by
  amazon.jobs itself (no auth, no scraping of rendered HTML).
- "unsupported": no reliable public structured endpoint was found during
  research (commonly because the company uses Workday, SuccessFactors,
  iCIMS, or a bespoke portal that requires a browser session/JS rendering,
  or blocks non-interactive access). These are intentionally left
  unimplemented rather than worked around - see README "Ethical scraping
  practices". They still appear here so the collection run reports them
  as skipped/unsupported instead of silently missing.

`ats_id` values for "greenhouse" and "lever" were verified by directly
querying the public API and confirming it returns real job data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CompanySource:
    name: str
    industry: str  # matches a key in config.keywords.INDUSTRY_KEYWORDS, or "other"
    ats: str  # "greenhouse" | "lever" | "amazon_jobs_api" | "unsupported"
    ats_id: Optional[str] = None
    notes: str = ""


COMPANIES: list[CompanySource] = [
    # --- Aerospace / defense ---------------------------------------
    CompanySource("Boeing", "aerospace_defense", "workday", "boeing/wd1/EXTERNAL_CAREERS"),
    CompanySource("Lockheed Martin", "aerospace_defense", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("Northrop Grumman", "aerospace_defense", "unsupported", notes="JS-rendered career site; ATS not identified via unauthenticated fetch."),
    CompanySource("RTX", "aerospace_defense", "unsupported", notes="Phenom-based portal; no public JSON API found."),
    CompanySource("GE Aerospace", "aerospace_defense", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("SpaceX", "aerospace_defense", "greenhouse", "spacex"),
    CompanySource("Blue Origin", "aerospace_defense", "lever", "blueorigin"),

    # --- Automotive / EV ---------------------------------------------
    CompanySource("Tesla", "automotive_ev", "unsupported", notes="Bespoke career portal; no public JSON API found."),
    CompanySource("Ford", "automotive_ev", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("General Motors", "automotive_ev", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("Rivian", "automotive_ev", "unsupported", notes="iCIMS-based portal; no public JSON API found."),
    CompanySource("Lucid", "automotive_ev", "greenhouse", "lucidmotors"),

    # --- Consumer hardware / tech --------------------------------------
    CompanySource("Apple", "consumer_hardware_tech", "unsupported", notes="Bespoke jobs.apple.com portal; no stable public API."),
    CompanySource("Microsoft", "consumer_hardware_tech", "unsupported", notes="Eightfold/SuccessFactors-based portal; no public JSON API found."),
    CompanySource("Amazon", "consumer_hardware_tech", "amazon_jobs_api", "amazon"),
    CompanySource("Google", "consumer_hardware_tech", "unsupported", notes="Bespoke careers portal; no public JSON API found."),
    CompanySource("Meta", "consumer_hardware_tech", "unsupported", notes="GraphQL-backed metacareers.com portal; no public JSON API found."),

    # --- Industrial / engineering --------------------------------------
    CompanySource("Caterpillar", "industrial_energy", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("John Deere", "industrial_energy", "unsupported", notes="JS-rendered career site; ATS not identified via unauthenticated fetch."),
    CompanySource("Siemens", "industrial_energy", "unsupported", notes="JS-rendered career site; ATS not identified via unauthenticated fetch."),
    CompanySource("Honeywell", "industrial_energy", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("Rockwell Automation", "industrial_energy", "workday", "rockwellautomation/wd1/External_Rockwell_Automation"),
    CompanySource("Emerson", "industrial_energy", "unsupported", notes="JS-rendered career site; ATS not identified via unauthenticated fetch."),
    CompanySource("Eaton", "industrial_energy", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("Parker Hannifin", "industrial_energy", "unsupported", notes="JS-rendered career site; ATS not identified via unauthenticated fetch."),

    # --- Medical devices ------------------------------------------------
    CompanySource("Medtronic", "medical_devices", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("Stryker", "medical_devices", "workday", "stryker/wd1/StrykerCareers"),
    CompanySource("Abbott", "medical_devices", "workday", "abbott/wd5/abbottcareers"),
    CompanySource("Boston Scientific", "medical_devices", "unsupported", notes="JS-rendered career site; Workday tenant not identified via unauthenticated fetch."),
    CompanySource("Johnson & Johnson", "medical_devices", "workday", "jj/wd5/JJ"),

    # --- Consulting -------------------------------------------------------
    CompanySource("McKinsey", "consulting", "unsupported", notes="Bespoke career portal; no public JSON API found."),
    CompanySource("BCG", "consulting", "greenhouse", "bcg"),
    CompanySource("Bain", "consulting", "unsupported", notes="Bespoke career portal; no public JSON API found."),
    CompanySource("Deloitte", "consulting", "unsupported", notes="Bespoke career portal; no public JSON API found."),
    CompanySource("Accenture", "consulting", "workday", "accenture/wd103/AccentureCareers"),
    CompanySource("EY", "consulting", "unsupported", notes="SuccessFactors-based portal; no public JSON API found."),
    CompanySource("PwC", "consulting", "unsupported", notes="Bespoke career portal; no public JSON API found."),
    CompanySource("KPMG", "consulting", "unsupported", notes="Bespoke career portal; no public JSON API found."),

    # --- Robotics / automation -------------------------------------------
    CompanySource("Boston Dynamics", "robotics_automation", "workday", "bostondynamics/wd1/Boston_Dynamics"),
    CompanySource("ABB", "robotics_automation", "unsupported", notes="Phenom-based portal; no public JSON API found."),
    CompanySource("FANUC", "robotics_automation", "unsupported", notes="Bespoke career portal; no public JSON API found."),
    CompanySource("Anduril", "robotics_automation", "greenhouse", "andurilindustries"),
    CompanySource("Applied Intuition", "robotics_automation", "ashby", "applied"),
]


def active_companies() -> list[CompanySource]:
    """Companies with a supported, working collector."""
    return [c for c in COMPANIES if c.ats != "unsupported"]


def unsupported_companies() -> list[CompanySource]:
    """Companies with no reliable public structured source (yet)."""
    return [c for c in COMPANIES if c.ats == "unsupported"]
