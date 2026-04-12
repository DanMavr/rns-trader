import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH  = DATA_DIR / "matd_backtest.db"

# ── Multi-ticker config ──────────────────────────────────────
TICKERS = {
    "MATD": {"yf": "MATD.L", "slug": "petro-matad-limited",            "name": "Petro Matad Limited"},
    "88E":  {"yf": "88E.L",  "slug": "88-energy-limited",              "name": "88 Energy Ltd"},
    "CHAR": {"yf": "CHAR.L", "slug": "chariot-limited",                "name": "Chariot Limited"},
    "PTAL": {"yf": "PTAL.L", "slug": "petrotal-corporation",           "name": "PetroTal Corporation"},
    "UJO":  {"yf": "UJO.L",  "slug": "union-jack-oil-plc",             "name": "Union Jack Oil plc"},
    "ZEN":  {"yf": "ZEN.L",  "slug": "zenith-energy-ltd",              "name": "Zenith Energy Ltd"},
    "BOR":  {"yf": "BOR.L",  "slug": "borders-southern-petroleum-plc", "name": "Borders & Southern Petroleum plc"},
    "AXL":  {"yf": "AXL.L",  "slug": "arrow-exploration-corp",         "name": "Arrow Exploration Corp"},
    "PANR": {"yf": "PANR.L", "slug": "pantheon-resources-plc",         "name": "Pantheon Resources plc"},
    "KIST": {"yf": "KIST.L", "slug": "kistos-holdings-plc",            "name": "Kistos Holdings plc"},
    "SOUC": {"yf": "SOUC.L", "slug": "southern-energy-corp",           "name": "Southern Energy Corp"},
    "BLOE": {"yf": "BLOE.L", "slug": "block-energy-plc",               "name": "Block Energy plc"},
}

DEFAULT_TICKER = "MATD"

# Backward compatibility — single ticker mode still works
TICKER      = DEFAULT_TICKER
TICKER_YF   = TICKERS[DEFAULT_TICKER]["yf"]
ISSUER_NAME = TICKERS[DEFAULT_TICKER]["slug"]

# ── LSE API ──────────────────────────────────────────────────
LSE_REFRESH_URL        = "https://api.londonstockexchange.com/api/v1/components/refresh"
LSE_HEADERS            = {"Referer": "https://www.londonstockexchange.com/",
                          "Content-Type": "application/json"}
NEWS_COMPONENT_ID      = "block_content%3A936265d4-63db-4cf3-a668-65d3c251be7f"
NEWS_LIST_COMPONENT_ID = "block_content%3A16061956-5f74-42e9-ad94-fb7c4457bef4"
NEWS_LIST_TAB_ID       = "a7bd00f8-7846-496a-8692-c55a0a24380c"

# ── Market hours (UK) ────────────────────────────────────────
MARKET_OPEN  = "08:00"
MARKET_CLOSE = "16:30"
TIMEZONE     = "Europe/London"

# ── Backtest ─────────────────────────────────────────────────
HOLD_MINUTES            = [5, 15, 30, 60]
TRADE_SCORE_THRESHOLD   = 2
TRADE_CONFIDENCE_NEEDED = "high"

# ── LLM — Grok ───────────────────────────────────────────────
XAI_API_KEY  = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL    = os.getenv("XAI_MODEL", "grok-4-1-fast-reasoning")
