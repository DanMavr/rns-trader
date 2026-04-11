# rns-trader

Automated RNS announcement scorer and backtester for AIM-listed stocks.

## What it does

1. Fetches full RNS announcement history from the LSE API
2. Retrieves complete announcement text for each filing
3. Scores each announcement using a local LLM (Ollama) from -2 to +2
4. Simulates paper trades based on score and confidence thresholds
5. Analyses win rates, returns, and patterns by announcement type

## Setup (Raspberry Pi)

```bash
git clone https://github.com/YOUR_USERNAME/rns-trader
cd rns-trader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Install Ollama and pull the model:
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
```

## Usage

```bash
# Start Ollama (needed for backtest step only)
ollama serve &

# Step 1: Collect all RNS + price data (~5 min)
python scripts/run_collect.py

# Step 2: Run backtest simulation (~20-40 min depending on Pi speed)
python scripts/run_backtest.py

# Step 3: View results report
python scripts/run_analyse.py
```

## First test (confirm API works from Pi)

```bash
python tests/test_rns_fetcher.py
```

All three tests should pass before running the full collection.

## Project structure

```
config/          All settings: ticker, thresholds, API keys, paths
src/collect/     LSE API fetching + Yahoo Finance prices + SQLite
src/score/       LLM scoring (Ollama / OpenAI / Anthropic fallback)
src/backtest/    Simulation loop + analysis report
src/monitor/     Live monitor (future — after backtest validated)
scripts/         Entry points: run_collect, run_backtest, run_analyse
data/            Local SQLite database (gitignored)
tests/           Integration tests
```

## Current configuration

- Ticker: MATD (Petro Matad Limited, AIM)
- LLM: Ollama llama3 (local, free)
- Price data: Yahoo Finance (daily 2yr + 5-min last 60 days)
- Trade threshold: score ±2, confidence = high
- Hold intervals measured: T+5, T+15, T+30, T+60, EOD
