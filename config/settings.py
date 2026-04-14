import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH  = DATA_DIR / "matd_backtest.db"

# ── Tickers ───────────────────────────────────────────────────────────────
# All slugs verified from live LSE URLs: londonstockexchange.com/stock/TICKER/slug/
# Verified: April 2026
# SAVE removed: suspended from AIM April 2024, corrupted price series
TICKERS = {
    # ── Original 11 ──────────────────────────────────────────────────────
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
    "BLOE": {"yf": "BLOE.L", "slug": "block-energy-plc",               "name": "Block Energy plc"},

    # ── Tier 1 additions — £20m-£750m, actively trading ─────────────────
    "RKH":  {"yf": "RKH.L",  "slug": "rockhopper-exploration-plc",     "name": "Rockhopper Exploration"},
    "ECO":  {"yf": "ECO.L",  "slug": "eco-atlantic-oil-gas-ltd",       "name": "Eco Atlantic Oil & Gas"},
    "AET":  {"yf": "AET.L",  "slug": "afentra-plc",                    "name": "Afentra"},
    "FOG":  {"yf": "FOG.L",  "slug": "falcon-oil-gas-ltd",             "name": "Falcon Oil & Gas"},
    "SEI":  {"yf": "SEI.L",  "slug": "sintana-energy-inc",             "name": "Sintana Energy"},
    "JSE":  {"yf": "JSE.L",  "slug": "jadestone-energy-plc",           "name": "Jadestone Energy"},
    "ZPHR": {"yf": "ZPHR.L", "slug": "zephyr-energy-plc",              "name": "Zephyr Energy"},
    "SEA":  {"yf": "SEA.L",  "slug": "seascape-energy-asia-plc",       "name": "Seascape Energy Asia"},
    "JOG":  {"yf": "JOG.L",  "slug": "jersey-oil-and-gas-plc",         "name": "Jersey Oil and Gas"},
    "TXP":  {"yf": "TXP.L",  "slug": "touchstone-exploration-inc",     "name": "Touchstone Exploration"},
    "PMG":  {"yf": "PMG.L",  "slug": "parkmead-group-the-plc",         "name": "Parkmead Group"},
    "STAR": {"yf": "STAR.L", "slug": "star-energy-group-plc",          "name": "Star Energy Group"},

    # ── Tier 2 additions — £8m-£55m, smaller/less liquid ────────────────
    "ENW":  {"yf": "ENW.L",  "slug": "enwell-energy-plc",              "name": "Enwell Energy"},
    "CASP": {"yf": "CASP.L", "slug": "caspian-sunrise-plc",            "name": "Caspian Sunrise"},
    "PXEN": {"yf": "PXEN.L", "slug": "prospex-energy-plc",             "name": "Prospex Energy"},
    "EOG":  {"yf": "EOG.L",  "slug": "europa-oil-gas-holdings-plc",    "name": "Europa Oil & Gas"},
    "ORCA": {"yf": "ORCA.L", "slug": "orcadian-energy-plc",            "name": "Orcadian Energy"},
    "EPP":  {"yf": "EPP.L",  "slug": "energypathways-plc",             "name": "EnergyPathways"},
    "SOU":  {"yf": "SOU.L",  "slug": "sound-energy-plc",               "name": "Sound Energy"},
    "UOG":  {"yf": "UOG.L",  "slug": "united-oil-gas-plc",             "name": "United Oil & Gas"},
}

DEFAULT_TICKER = "MATD"

# Backward compatibility
TICKER      = DEFAULT_TICKER
TICKER_YF   = TICKERS[DEFAULT_TICKER]["yf"]
ISSUER_NAME = TICKERS[DEFAULT_TICKER]["slug"]

# ── LSE API ──────────────────────────────────────────────────────────────
LSE_REFRESH_URL        = "https://api.londonstockexchange.com/api/v1/components/refresh"
LSE_HEADERS            = {"Referer": "https://www.londonstockexchange.com/",
                          "Content-Type": "application/json"}
NEWS_COMPONENT_ID      = "block_content%3A936265d4-63db-4cf3-a668-65d3c251be7f"
NEWS_LIST_COMPONENT_ID = "block_content%3A16061956-5f74-42e9-ad94-fb7c4457bef4"
NEWS_LIST_TAB_ID       = "a7bd00f8-7846-496a-8692-c55a0a24380c"

# ── Market hours (UK) ────────────────────────────────────────────────────
MARKET_OPEN  = "08:00"
MARKET_CLOSE = "16:30"
TIMEZONE     = "Europe/London"

# ── Signal thresholds (derived from data analysis Apr 2026) ─────────────
VOL_MULTIPLIER   = 3.0   # daily volume must be Nx above 20d average
PRICE_MOVE_PCT   = 2.0   # (close-open)/open must exceed this % on RNS day
MIN_HISTORY_DAYS = 5     # minimum prior bars needed for avg_vol baseline

# ── LLM — Grok (optional, only used with --llm flag) ────────────────────
XAI_API_KEY  = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL    = os.getenv("XAI_MODEL", "grok-4-1-fast-reasoning")
