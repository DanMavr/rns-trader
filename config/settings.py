import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH  = DATA_DIR / "matd_backtest.db"

# Target ticker
TICKER        = "MATD"
TICKER_YF     = "MATD.L"       # Yahoo Finance format
ISSUER_NAME   = "petro-matad-limited"

# LSE API
LSE_REFRESH_URL = "https://api.londonstockexchange.com/api/v1/components/refresh"
LSE_ALLDATA_URL = "https://api.londonstockexchange.com/api/gw/lse/instruments/alldata/{ticker}"
LSE_HEADERS     = {"Referer": "https://www.londonstockexchange.com/",
                   "Content-Type": "application/json"}
NEWS_COMPONENT_ID = "block_content%3A936265d4-63db-4cf3-a668-65d3c251be7f"
NEWS_LIST_COMPONENT_ID = "block_content%3A16061956-5f74-42e9-ad94-fb7c4457bef4"
NEWS_LIST_TAB_ID = "a7bd00f8-7846-496a-8692-c55a0a24380c"

# Market hours (UK)
MARKET_OPEN  = "08:00"
MARKET_CLOSE = "16:30"
TIMEZONE     = "Europe/London"

# Backtest
HOLD_MINUTES  = [5, 15, 30, 60]   # measure returns at these intervals
TRADE_SCORE_THRESHOLD   = 2       # only trade on ±2
TRADE_CONFIDENCE_NEEDED = "high"  # only trade on high confidence

# LLM
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
