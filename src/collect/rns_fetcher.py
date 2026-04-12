import time
import requests
from config.settings import (
    LSE_REFRESH_URL, LSE_HEADERS,
    NEWS_COMPONENT_ID, NEWS_LIST_COMPONENT_ID,
    NEWS_LIST_TAB_ID, TICKER, ISSUER_NAME
)
from src.collect.database import get_connection
from src.collect.html_cleaner import clean_html


def fetch_rns_list(ticker=TICKER, issuer_name=ISSUER_NAME, max_pages=20):
    """Fetch paginated RNS list for a ticker from the LSE API."""
    all_items = []
    page = 0

    while page < max_pages:
        payload = {
            "path": "issuer-profile",
            "parameters": (
                f"tidm%3D{ticker}"
                f"%26tab%3Danalysis"
                f"%26issuername%3D{issuer_name}"
                f"%26tabId%3D{NEWS_LIST_TAB_ID}"
            ),
            "components": [{
                "componentId": NEWS_LIST_COMPONENT_ID,
                "parameters": f"page={page}&size=20"
            }]
        }
        r = requests.post(LSE_REFRESH_URL, json=payload,
                          headers=LSE_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        comp = next(
            (c for c in data if c.get("type") == "news-table-issuer-profile"),
            None
        )
        if not comp:
            print(f"  No news-table component on page {page}")
            break

        val = comp["content"][0]["value"]
        if not val:
            break

        items = val.get("content", [])
        all_items.extend(items)
        total_pages = val.get("totalPages", 1)
        print(f"  Page {page + 1}/{total_pages}: {len(items)} items fetched")

        if val.get("last", True):
            break

        page += 1
        time.sleep(1)

    return all_items


def fetch_rns_body(news_id):
    """Fetch full RNS body for a single announcement."""
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

    comp = next(
        (c for c in data if c.get("type") == "news-article-content"),
        None
    )
    if not comp:
        return None

    val = next(
        (x["value"] for x in comp["content"] if x["name"] == "newsarticle"),
        None
    )
    return val


def save_rns_list(items, ticker=TICKER):
    """Insert RNS list items into the database, skipping duplicates."""
    conn = get_connection()
    inserted = 0
    for item in items:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO rns_events
                    (id, ticker, rnsnumber, category, headlinename, title, datetime)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item["id"],
                ticker,
                item.get("rnsnumber"),
                item.get("category"),
                item.get("headlinename"),
                item.get("title"),
                item.get("datetime"),
            ))
            if conn.total_changes:
                inserted += 1
        except Exception as e:
            print(f"  Error inserting id={item.get('id')}: {e}")
    conn.commit()
    conn.close()
    print(f"  {inserted} new items saved to database")


def enrich_rns_bodies(ticker=None, delay=2.0):
    """
    Fetch full body text for all pending rns_events.
    Optionally filter by ticker.
    """
    conn = get_connection()
    if ticker:
        rows = conn.execute("""
            SELECT id, title FROM rns_events
            WHERE fetch_status = 'pending' AND ticker = ?
            ORDER BY datetime DESC
        """, (ticker,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, title FROM rns_events
            WHERE fetch_status = 'pending'
            ORDER BY datetime DESC
        """).fetchall()
    conn.close()

    total = len(rows)
    print(f"  {total} announcements to enrich...")

    for i, row in enumerate(rows, 1):
        news_id = row["id"]
        title   = row["title"] or ""
        print(f"  [{i}/{total}] {news_id} — {title[:50]}")

        try:
            val = fetch_rns_body(news_id)
            if not val:
                status    = "no_content"
                body_text = None
                headline  = None
            else:
                raw_body  = val.get("body", "") or ""
                body_text = clean_html(raw_body)
                headline  = val.get("headlineName") or val.get("headlinename")
                status    = "ok"
        except Exception as e:
            print(f"    Error: {e}")
            status    = "error"
            body_text = None
            headline  = None

        conn = get_connection()
        conn.execute("""
            UPDATE rns_events
            SET fetch_status=?, body_text=?,
                headlinename=COALESCE(headlinename, ?)
            WHERE id=?
        """, (status, body_text, headline, news_id))
        conn.commit()
        conn.close()

        if i < total:
            time.sleep(delay)
