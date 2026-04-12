"""
Category filter — eliminates RNS categories that never produce
tradeable reactions. One byte of data, zero compute, ~40% noise
reduction before any price/volume analysis begins.
"""

# Categories to skip entirely — routine admin, no price impact
SKIP_CATEGORIES = {
    "NOA",  # Notice of AGM
    "RAG",  # Result of AGM
    "BOA",  # Board/Director change (minor)
    "NRA",  # Non-Regulatory Announcement
    "AGR",  # Agreement (too varied, mostly routine)
}

# Categories that are always worth watching
HIGH_PRIORITY = {
    "DRL",  # Drilling / Production Report — binary catalyst
    "FR",   # Final Results — high impact
    "IR",   # Interim Results — high impact
    "ROI",  # Result of Issue — confirms capital raise complete
}

# Categories that need context
WATCH_CATEGORIES = {
    "UPD",  # Operational Update — could be anything
    "IOE",  # Issue of Equity — usually mildly negative
    "MSC",  # Miscellaneous — could be major
}


def should_skip(category: str) -> bool:
    """Return True if this category should be skipped entirely."""
    return (category or "").upper() in SKIP_CATEGORIES


def get_priority(category: str) -> str:
    """Return 'high', 'watch', or 'skip' for a category code."""
    cat = (category or "").upper()
    if cat in HIGH_PRIORITY:
        return "high"
    if cat in WATCH_CATEGORIES:
        return "watch"
    if cat in SKIP_CATEGORIES:
        return "skip"
    return "watch"
