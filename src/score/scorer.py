import json
from config.settings import XAI_API_KEY, XAI_BASE_URL, XAI_MODEL
from src.score.prompts import SYSTEM_PROMPT, build_user_prompt


def score_rns(ticker, company_name, category, headlinename, title, body_text):
    """
    Score an RNS announcement using Grok.
    Returns dict: {score, confidence, reason} or None on failure.
    """
    if not XAI_API_KEY:
        print("  ERROR: XAI_API_KEY not set in .env")
        return None

    prompt = build_user_prompt(
        ticker, company_name, category, headlinename, title, body_text
    )

    return _score_grok(prompt)


def _parse_llm_response(text):
    """Extract and parse JSON from LLM response text."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    try:
        start = text.index("{")
        end   = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def _score_grok(prompt):
    """Score using xAI Grok via OpenAI-compatible API."""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=XAI_API_KEY,
            base_url=XAI_BASE_URL,
        )
        response = client.chat.completions.create(
            model=XAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        text   = response.choices[0].message.content
        result = _parse_llm_response(text)
        if result:
            print(f"  [Grok {XAI_MODEL}] {result}")
        else:
            print(f"  [Grok] Could not parse response: {text[:100]}")
        return result
    except Exception as e:
        print(f"  Grok error: {e}")
        return None
