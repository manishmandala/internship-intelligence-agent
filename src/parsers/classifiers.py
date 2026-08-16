"""
Keyword-based classification of a posting into a role category and an
industry category. Pure functions, no I/O, easy to unit test.
"""
from __future__ import annotations

from config.keywords import INDUSTRY_KEYWORDS, ROLE_CATEGORY_KEYWORDS


def _count_hits(text_lower: str, keyword_map: dict[str, list[str]]) -> dict[str, int]:
    return {
        key: sum(1 for kw in keywords if kw in text_lower)
        for key, keywords in keyword_map.items()
    }


def _best_match(text: str, keyword_map: dict[str, list[str]], default: str) -> str:
    """Return the key in `keyword_map` whose keyword list has the most hits
    in `text`. Ties go to whichever key was defined first (dict order).
    """
    hits = _count_hits(text.lower(), keyword_map)
    best_key = max(hits, key=hits.get)
    return best_key if hits[best_key] > 0 else default


def classify_role_category(title: str, description: str) -> str:
    """Classify a posting's role category, trusting the title far more
    than the description body.

    A long job description often name-drops unrelated disciplines in
    company-overview boilerplate (e.g. an HR "Recruiting Coordinator"
    posting that describes SpaceX's "autonomous flight" programs). If we
    scored title and description equally, a single incidental mention in
    the body could out-vote a title with zero relevant keywords. So: if
    the title alone clearly signals a category, trust it. Otherwise fall
    back to the description, but require at least 2 keyword hits there
    before overriding "other" - one passing mention isn't enough signal.
    """
    title_hits = _count_hits(title.lower(), ROLE_CATEGORY_KEYWORDS)
    best_title_key = max(title_hits, key=title_hits.get)
    if title_hits[best_title_key] > 0:
        return best_title_key

    description_hits = _count_hits(description.lower(), ROLE_CATEGORY_KEYWORDS)
    best_description_key = max(description_hits, key=description_hits.get)
    if description_hits[best_description_key] >= 2:
        return best_description_key

    return "other"


def classify_industry(company: str, title: str, description: str) -> str:
    text = f"{company} {company} {title} {description}"  # weight company 2x
    return _best_match(text, INDUSTRY_KEYWORDS, default="other")
