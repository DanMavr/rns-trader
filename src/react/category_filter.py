"""
Category filter — eliminates RNS categories that never produce
tradeable reactions. One lookup, zero compute, ~10% noise reduction
before any price/volume analysis begins.

Category codes observed across 11 AIM oil & gas tickers:
  High catalyst  : DRL, FR, IR, ROI, PFU
  Worth watching : UPD, IOE, MSC, ACQ, TR
  Routine admin  : NOA, RAG, BOA, NRA, AGR, HOL, DSH, BOD
"""

# Categories to skip entirely — no material price impact expected
SKIP_CATEGORIES = {
    "NOA",  # Notice of AGM
    "RAG",  # Result of AGM
    "BOA",  # Board/Director change (minor)
    "BOD",  # Board changes
    "NRA",  # Non-Regulatory Announcement
    "AGR",  # Agreement (usually routine)
    "HOL",  # Holding(s) in Company — passive disclosure
    "DSH",  # Director Shareholding — passive disclosure
}

# Categories that are always high-priority catalysts
HIGH_PRIORITY = {
    "DRL",  # Drilling / Production Report — binary catalyst
    "FR",   # Final Results — high impact
    "IR",   # Interim Results — high impact
    "ROI",  # Result of Issue — confirms capital raise complete
    "PFU",  # Production / Financial Update — material operational news
}

# Categories that need market confirmation to be tradeable
WATCH_CATEGORIES = {
    "UPD",  # Operational Update — could be anything
    "IOE",  # Issue of Equity — usually dilutive
    "MSC",  # Miscellaneous — could be major or minor
    "ACQ",  # Acquisition / disposal — material corporate event
    "TR",   # Trading / Revenue update
}


def should_skip(category: str) -> bool:
    """Return True if this category should be skipped entirely."""
    return (category or "").upper() in SKIP_CATEGORIES


def get_priority(category: str) -> str:
    """
    Return priority string for a category code.
    Unknown categories default to 'watch' — we err on the side of
    inclusion and let the reaction detector filter them out.
    """
    cat = (category or "").upper()
    if cat in HIGH_PRIORITY:
        return "high"
    if cat in SKIP_CATEGORIES:
        return "skip"
    if cat in WATCH_CATEGORIES:
        return "watch"
    # Unknown category — include but flag
    return "watch"
