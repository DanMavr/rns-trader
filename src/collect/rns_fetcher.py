import requests
import time
from config.settings import (LSE_REFRESH_URL, LSE_HEADERS,
                               NEWS_COMPONENT_ID, NEWS_LIST_COMPONENT_ID,
                               NEWS_LIST_TAB_ID, TICKER, ISSUER_NAME)
from src.collect.database import get_connection

def fetch_rns_list(ticker=TICKER, issuer_name=ISSUER_NAME, max_pages=5):
    """Fetch paginated RNS list for a ticker. Returns list of dicts."""
    all_items = []
    page = 0

    while page < max_pages:
        payload = {
            "path": "issuer-profile",
            "parameters": f"tidm%3D{ticker}%26tab%3Danalysis%26issuername%3D{issuer_name}%26tabId%3D{NEWS_LIST_TAB_ID}",
            "components": [{
                "componentId": NEWS_LIST_COMPONENT_ID,
                "parameters": f"page={page}&size=20"
            }]
        }
        r = requests.post(LSE_REFRESH_URL, json=payload,
                          headers=LSE_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        comp = next((c for c in data if c.get("type") == "news-table-issuer-profile"), None)
        if not comp:
            break

        val = comp["content"][0]["value"]
        items = val.get("content", [])
        all_items.extend(items)

        total_pages = val.get("totalPages", 1)
        print(f"  Page {page+1}/{total_pages}: {len(items)} items")

        if val.get("last", True):
            break
        page += 1
        time.sleep(1)

    return all_items


def fetch_rns_body(news_id):
    """Fetch full HTML body for a single RNS by its numeric newsId."""
    payload = {
        "path": "news-article",
        "parameters": f"newsId%3D{news_id}",
        "components": [{
            "componentId": NEWS_COMPONENT_ID,
            "parameters": None
        }]
    }
    r = requests.post(LSE_REFRESH_URL, json=payload,
                      headers=LSE_HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()

    comp = next((c for c in data if c.get("type") == "news-article-content"), None)
    if not comp:
        return None

    val = next((x["value"] for x in comp["content"]
                if x["name"] == "newsarticle"), None)
    return val  # full dict with body, title, datetime, rnsnumber etc.


def save_rns_list(items, ticker=TICKER):
    """Insert RNS list items into database (skip duplicates)."""
    conn = get_connection()
    c = conn.cursor()
    inserted = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR IGNORE INTO rns_events
                    (id, ticker, rnsnumber, category, title, datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item["id"], ticker, item.get("rnsnumber"),
                  item.get("category"), item.get("title"),
                  item.get("datetime")))
            if c.rowcount:
                inserted += 1
        except Exception as e:
            print(f"  Error inserting {item.get('id')}: {e}")
    conn.commit()
    conn.close()
    print(f"  Saved {inserted} new items to database")


def enrich_rns_bodies(delay=2.0):
    """Fetch body text for all rns_events where fetch_status='pending'."""
    from src.collect.html_cleaner import clean_html
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title FROM rns_events WHERE fetch_status='pending' ORDER BY datetime DESC"
    ).fetchall()
    conn.close()

    print(f"Fetching body text for {len(rows)} announcements...")

    for i, row in enumerate(rows):
        news_id = row["id"]
        print(f"  [{i+1}/{len(rows)}] id={news_id} — {row['title'][:50]}")
        try:
            result = fetch_rns_body(news_id)
            conn = get_connection()
            if result and result.get("body"):
                body_text = clean_html(result["body"])
                conn.execute("""
                    UPDATE rns_events SET
                        body_html    = ?,
                        body_text    = ?,
                        headlinename = ?,
                        fetch_status = 'ok'
                    WHERE id = ?
                """, (result["body"], body_text,
                      result.get("headlinename"), news_id))
                print(f"    ✓ {len(body_text)} chars")
            else:
                conn.execute("UPDATE rns_events SET fetch_status='null' WHERE id=?",
                             (news_id,))
                print(f"    ✗ null body")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(delay)
