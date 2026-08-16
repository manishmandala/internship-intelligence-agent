"""
Text cleaning helpers shared by every parser.

Job descriptions arrive as HTML from every ATS we support. We convert to
clean plain text once here, rather than in each parser, so scoring and
skills-extraction always operate on consistent input.
"""
from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    """Strip HTML tags and collapse whitespace into a readable plain-text
    block. Returns an empty string for empty/None input.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator="\n")
    # Collapse 3+ blank lines down to a single blank line, and strip
    # trailing spaces on each line.
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


# Headings commonly used to separate a "requirements" style section from
# the rest of a posting. Matched case-insensitively at the start of a line.
_QUALIFICATION_HEADINGS = [
    "basic qualifications", "minimum qualifications", "requirements",
    "required qualifications", "what you'll need", "what you will need",
    "qualifications", "who you are", "you have", "you'll need",
]
_PREFERRED_HEADINGS = [
    "preferred qualifications", "nice to have", "bonus points",
    "preferred skills", "what will set you apart",
]


def split_qualifications(full_text: str) -> tuple[str, str]:
    """Best-effort split of a job description into (required, preferred)
    qualification blocks, based on common section headings.

    This is a heuristic, not a guarantee - postings are not standardized.
    If no heading is found, both return values are empty strings and the
    caller should fall back to using the full description for matching.
    """
    if not full_text:
        return "", ""

    lines = full_text.splitlines()
    required_lines: list[str] = []
    preferred_lines: list[str] = []
    current_bucket: Optional[list[str]] = None

    for line in lines:
        lowered = line.strip().lower().rstrip(":")
        if any(lowered == h or lowered.startswith(h) for h in _PREFERRED_HEADINGS):
            current_bucket = preferred_lines
            continue
        if any(lowered == h or lowered.startswith(h) for h in _QUALIFICATION_HEADINGS):
            current_bucket = required_lines
            continue
        # A short, title-cased line with no trailing punctuation often
        # marks the start of a new (unrelated) section - stop collecting.
        if current_bucket is not None and len(line) < 60 and line.strip().endswith(":"):
            current_bucket = None
        if current_bucket is not None:
            current_bucket.append(line)

    return "\n".join(required_lines).strip(), "\n".join(preferred_lines).strip()


def classify_employment_type(title: str, description: str) -> str:
    """Guess whether a posting is an Internship or Co-op from its title
    and description text.
    """
    text = f"{title} {description}".lower()
    if "co-op" in text or "coop" in text or "co op" in text:
        return "Co-op"
    if "intern" in text:
        return "Internship"
    return "Unknown"
