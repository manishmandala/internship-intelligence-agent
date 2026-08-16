"""
Tunable constants for the rule-based scorer. Splitting these out from
`scorer.py` means re-weighting "what matters" never requires touching
scoring logic itself.
"""
from __future__ import annotations

# How much each sub-score contributes to the overall 0-100 fit_score.
# Must sum to 1.0.
SCORE_WEIGHTS = {
    "role_fit": 0.30,
    "industry_fit": 0.20,
    "eligibility_fit": 0.15,
    "skills_fit": 0.15,
    "location_fit": 0.20,
}

# Role categories the candidate is NOT interested in still get *some*
# credit if the posting is at least engineering/technical-adjacent, but
# "other" (e.g. marketing, finance, sales intern) scores low.
ROLE_FIT_SCORES = {
    "mechanical_design": 100,
    "manufacturing": 95,
    "robotics_ai_hardware": 95,
    "product_program_management": 90,
    "consulting_strategy": 85,
    "other": 20,
}

INDUSTRY_FIT_SCORES = {
    "aerospace_defense": 100,
    "automotive_ev": 95,
    "medical_devices": 90,
    "robotics_automation": 95,
    "industrial_energy": 90,
    "consumer_hardware_tech": 85,
    "consulting": 80,
    "other": 35,
}

# Fit score threshold at/above which a posting is flagged as "high value".
HIGH_VALUE_FLAG_THRESHOLD = 85

# A posting with a known application deadline within this many days is
# flagged as time-sensitive.
TIME_SENSITIVE_DEADLINE_DAYS = 14

# Grad years a posting's stated eligibility window is checked against.
GRAD_YEAR_SEARCH_RANGE = (2024, 2032)
