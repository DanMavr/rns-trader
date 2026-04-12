"""
Tests for the reaction system.
Run: python tests/test_reaction.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_category_filter():
    from src.react.category_filter import should_skip, get_priority
    assert should_skip("NOA") == True
    assert should_skip("DRL") == False
    assert get_priority("DRL") == "high"
    assert get_priority("NOA") == "skip"
    assert get_priority("UPD") == "watch"
    print("  PASS category_filter")


def test_classify_timing():
    from src.react.reaction_detector import classify_timing
    assert classify_timing("2025-09-29T07:00:00") == "pre_market"
    assert classify_timing("2025-09-29T09:30:00") == "intraday"
    assert classify_timing("2025-09-29T17:00:00") == "post_market"
    print("  PASS classify_timing")


def test_20d_avg_volume():
    from src.react.reaction_detector import get_20d_avg_volume
    vol = get_20d_avg_volume("MATD", "2025-09-29")
    print(f"  20d avg vol before 2025-09-29: {vol:,.0f}")
    assert vol >= 0
    print("  PASS get_20d_avg_volume")


def test_price_context():
    from src.react.context_filter import get_price_context
    ctx = get_price_context("MATD", "2025-09-29")
    print(f"  Context: {ctx}")
    assert "setup_quality" in ctx
    print("  PASS price_context")


def test_reaction_detector():
    from src.react.reaction_detector import detect_reaction
    result = detect_reaction("MATD", "2025-09-29T06:05:00")
    print(f"  Result: triggered={result['triggered']} "
          f"strength={result['strength']}× "
          f"bars={result['bars_found']} "
          f"price={result['price_change_pct']:+.2f}%")
    print("  PASS reaction_detector")


if __name__ == "__main__":
    print("Running reaction system tests...\n")
    test_category_filter()
    test_classify_timing()
    test_20d_avg_volume()
    test_price_context()
    test_reaction_detector()
    print("\nAll tests passed.")
