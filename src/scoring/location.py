"""
Heuristic US-vs-not-US classification for a free-text location string.

Company job boards (Greenhouse/Lever especially) list openings from every
office worldwide, so this matters a lot for a candidate who is only
willing to work in the United States.
"""
from __future__ import annotations

US_STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia",
}

US_SIGNAL_PHRASES = {
    "united states", "usa", "u.s.", "u.s.a", "remote - us", "remote (us)",
    "remote, us", "remote us",
}

# Substrings that reliably indicate a non-US office. Kept short and
# specific to avoid false positives against US city/company names.
NON_US_SIGNAL_PHRASES = {
    "united kingdom", "england", "scotland", "canada", "mexico", "germany",
    "france", "spain", "italy", "netherlands", "poland", "ireland",
    "india", "china", "japan", "singapore", "australia", "brazil",
    "saudi arabia", "united arab emirates", "israel", "switzerland",
    "sweden", "norway", "denmark", "finland", "belgium", "austria",
    "portugal", "czech", "romania", "hungary", "greece", "korea",
    "taiwan", "vietnam", "thailand", "philippines", "malaysia",
    "indonesia", "new zealand", "south africa", "egypt", "turkey",
    "argentina", "chile", "colombia", "costa rica", "peru",
}


def classify_us_location(location: str) -> str:
    """Returns "us", "non_us", or "unknown" for a raw location string."""
    if not location or location.strip().lower() in {"unknown", ""}:
        return "unknown"

    text = location.lower()

    if any(phrase in text for phrase in NON_US_SIGNAL_PHRASES):
        return "non_us"

    if any(phrase in text for phrase in US_SIGNAL_PHRASES):
        return "us"

    if any(name in text for name in US_STATE_NAMES):
        return "us"

    # Match a 2-letter state abbreviation as its own token, e.g.
    # "Columbus, OH" - but not the "OH" inside another word.
    tokens = [t.strip(",.() ") for t in text.upper().split()]
    if any(t in US_STATE_ABBREVIATIONS for t in tokens):
        return "us"

    return "unknown"
