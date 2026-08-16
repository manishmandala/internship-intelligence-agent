"""
Keyword and skill vocabularies used by search, filtering, scoring, and the
skills-analysis module.

Keeping these lists in one place means the scoring logic in
`src/scoring/scorer.py` never has hard-coded strings scattered through it -
tuning the project's behavior is mostly a matter of editing this file.
"""

# Title/description keywords used to decide whether a posting is even worth
# keeping, and to bucket it into a role category for filtering.
SEARCH_KEYWORDS = [
    "mechanical engineering intern",
    "manufacturing engineering intern",
    "product engineering intern",
    "design engineering intern",
    "robotics intern",
    "hardware engineering intern",
    "technical consulting intern",
    "strategy intern",
    "product management intern",
    "program management intern",
]

# Note: the internship/co-op title pre-filter itself lives in
# src/parsers/job_parser.py as a word-boundary regex (a plain substring
# check for "intern" also matches "Internal", "International", etc).

# Role category -> keywords that indicate that category. Order matters only
# in that the first matching category with the highest keyword hit-count
# wins (see scoring/rules.py).
ROLE_CATEGORY_KEYWORDS = {
    "mechanical_design": [
        "mechanical engineer", "mechanical engineering", "design engineer",
        "design engineering", "cad", "gd&t", "fea", "structural analysis",
        "prototyping", "product design",
    ],
    "manufacturing": [
        "manufacturing engineer", "manufacturing engineering", "process engineer",
        "process engineering", "production engineer", "industrial engineer",
        "quality engineer", "cnc", "lean manufacturing", "six sigma",
        "assembly line", "tooling",
    ],
    "robotics_ai_hardware": [
        "robotics", "autonomy", "autonomous", "controls engineer",
        "hardware engineer", "hardware engineering", "embedded", "mechatronics",
        "electromechanical", "perception", "ros", "machine learning", "ai engineer",
    ],
    "product_program_management": [
        "product manager", "product management", "program manager",
        "program management", "project manager", "project management",
        "technical program manager", "apm", "product owner",
    ],
    "consulting_strategy": [
        "consultant", "consulting", "strategy intern", "strategy analyst",
        "business analyst", "corporate strategy", "management consulting",
        "technical consulting",
    ],
}

# Industry keywords, matched against company name / description, used for
# both the "industry" column and industry-fit scoring.
INDUSTRY_KEYWORDS = {
    "aerospace_defense": [
        "aerospace", "defense", "spacecraft", "satellite", "aircraft",
        "avionics", "propulsion", "missile", "space systems",
    ],
    "automotive_ev": [
        "automotive", "electric vehicle", "ev battery", "vehicle dynamics",
        "powertrain", "battery pack", "adas",
    ],
    "consumer_hardware_tech": [
        "consumer electronics", "consumer hardware", "wearable", "smartphone",
        "device design",
    ],
    "industrial_energy": [
        "industrial automation", "heavy equipment", "power generation",
        "renewable energy", "hvac", "turbine", "energy storage", "grid",
        "industrial equipment",
    ],
    "medical_devices": [
        "medical device", "biomedical", "surgical", "diagnostics",
        "implant", "fda", "clinical",
    ],
    "consulting": [
        "consulting", "professional services", "advisory",
    ],
    "robotics_automation": [
        "robotics", "automation", "industrial robot", "cobots",
    ],
}

# Skills to extract from job descriptions/qualifications. Matching is case
# insensitive; word-boundary regex is applied at extraction time (see
# src/analysis/skills.py) so short tokens like "R" or "C" won't be added
# without care.
SKILL_VOCABULARY = [
    "Python", "MATLAB", "SolidWorks", "Creo", "CATIA", "CAD", "GD&T", "FEA",
    "ANSYS", "Manufacturing", "CNC", "Robotics", "ROS", "C++", "C",
    "SQL", "Excel", "Data Analysis", "Project Management", "Communication",
    "AutoCAD", "NX", "Fusion 360", "3D Printing", "Additive Manufacturing",
    "Six Sigma", "Lean Manufacturing", "PLC", "LabVIEW", "R", "Java",
    "PowerPoint", "Tableau", "JIRA", "Machine Learning", "Circuit Design",
    "Embedded Systems", "Thermodynamics", "Fluid Dynamics", "Statics",
]

# Skills considered strong signals of fit for this specific candidate
# profile - used as a bonus in the skills-fit sub-score.
HIGH_VALUE_SKILLS = {
    "SolidWorks", "Creo", "CATIA", "CAD", "GD&T", "FEA", "ANSYS",
    "Manufacturing", "CNC", "Robotics", "ROS", "MATLAB", "Python",
    "Fusion 360", "3D Printing", "Additive Manufacturing", "Six Sigma",
}

# Phrases that suggest a role is especially selective / prestigious. Used
# for the "flag as valuable/selective" heuristic.
SELECTIVE_SIGNAL_PHRASES = [
    "highly selective", "limited positions", "competitive process",
    "rotational program", "leadership development program",
    "fellows program", "scholars program", "elite", "invite only",
]

# Phrases suggesting eligibility restrictions worth surfacing to the user
# (not automatically disqualifying, since this candidate is early-career).
ELIGIBILITY_SIGNAL_PHRASES = [
    "rising junior", "rising senior", "junior or senior",
    "graduating in", "expected graduation", "class of",
    "penultimate year", "final year",
]
