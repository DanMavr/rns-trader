"""
Basic integration tests — confirm API calls work from the Pi.
Run: python tests/test_rns_fetcher.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_fetch_rns_body():
    from src.collect.rns_fetcher import fetch_rns_body
    result = fetch_rns_body(17465485)
    assert result is not None, "fetch_rns_body returned None"
    assert result.get("body"), "body field is empty"
    assert "Petro Matad" in result["body"], "Company name not in body"
    assert result["rnsnumber"] == "4080T"
    print(f"  PASS fetch_rns_body: {len(result['body'])} chars, "
          f"rnsnumber={result['rnsnumber']}")


def test_clean_html():
    from src.collect.html_cleaner import clean_html
    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    out  = clean_html(html)
    assert "Hello" in out and "world" in out
    assert "<" not in out
    print(f"  PASS clean_html: '{out}'")


def test_fetch_rns_list():
    from src.collect.rns_fetcher import fetch_rns_list
    items = fetch_rns_list(max_pages=1)
    assert len(items) > 0, "RNS list is empty"
    assert "id" in items[0]
    assert "title" in items[0]
    print(f"  PASS fetch_rns_list: {len(items)} items on page 1")


if __name__ == "__main__":
    print("Running integration tests...")
    test_clean_html()
    test_fetch_rns_body()
    test_fetch_rns_list()
    print("\nAll tests passed.")
