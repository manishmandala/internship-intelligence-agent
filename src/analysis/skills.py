"""
Skill extraction from free-text job descriptions/qualifications.

Uses simple regex word-boundary matching against `SKILL_VOCABULARY`
(config/keywords.py) rather than NLP/ML, matching the project's "rule-based,
no paid API required" design.
"""
from __future__ import annotations

import re

from config.keywords import SKILL_VOCABULARY

# \b word-boundary breaks on things like "+" and "&", so skills containing
# them (C++, GD&T) need a hand-built pattern instead of \bSKILL\b.
#
# "C" and "R" get their own narrow, phrase-based patterns rather than a
# plain \bC\b / \bR\b: a bare word-boundary match on a single letter fires
# on things that have nothing to do with the programming language, e.g.
# "8 U.S.C. 1101" (contains a standalone "C") or "our R&D team" (contains
# a standalone "R"). Both are common in real job postings' legal/org
# boilerplate, so single-letter languages are only counted when they show
# up in a recognizable language-list phrasing.
_SPECIAL_PATTERNS = {
    "C++": re.compile(r"(?<![A-Za-z0-9])C\+\+(?![A-Za-z0-9])", re.IGNORECASE),
    "GD&T": re.compile(r"(?<![A-Za-z0-9])GD\s*&\s*T(?![A-Za-z0-9])", re.IGNORECASE),
    "C": re.compile(
        r"\bC\s*/\s*C\+\+|\bC\+\+\s*/\s*C\b|\bC\s+or\s+C\+\+\b|\bC\s+and\s+C\+\+\b"
        r"|\bC\s*,\s*C\+\+\b|\bC\+\+\s*,\s*C\b|\bC\s+programming\b|\bC\s+language\b",
        re.IGNORECASE,
    ),
    "R": re.compile(
        r"\bR\s+programming\b|\bR\s+language\b|\bR\s*/\s*Python\b|\bPython\s*/\s*R\b"
        r"|\bPython\s*,\s*R\b|\bR\s*,\s*Python\b|\bSQL\s*,\s*R\b|\bR\s*,\s*SQL\b",
        re.IGNORECASE,
    ),
}


def _build_pattern(skill: str) -> re.Pattern:
    if skill in _SPECIAL_PATTERNS:
        return _SPECIAL_PATTERNS[skill]
    escaped = re.escape(skill)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


_SKILL_PATTERNS: dict[str, re.Pattern] = {skill: _build_pattern(skill) for skill in SKILL_VOCABULARY}


def extract_skills(text: str) -> list[str]:
    """Return the subset of SKILL_VOCABULARY found in `text`, preserving
    the vocabulary's canonical casing (e.g. always "SolidWorks", never
    "solidworks") and original order.
    """
    if not text:
        return []

    found: list[str] = []
    for skill, pattern in _SKILL_PATTERNS.items():
        if pattern.search(text):
            found.append(skill)
    return found
