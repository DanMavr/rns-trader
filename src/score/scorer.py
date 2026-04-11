import json
from config.settings import OLLAMA_HOST, OLLAMA_MODEL, OPENAI_API_KEY, ANTHROPIC_API_KEY
from src.score.prompts import SYSTEM_PROMPT, build_user_prompt


def score_rns(ticker, company_name, category, headlinename, title, body_text):
    """
    Score an RNS announcement using available LLM.
    Returns dict: {score, confidence, reason} or None on failure.
    Tries Ollama first, falls back to OpenAI then Anthropic.
    """
    prompt = build_user_prompt(
        ticker, company_name, category, headlinename, title, body_text
    )

    result = _score_ollama(prompt)
    if result:
        return result

    if OPENAI_API_KEY:
        result = _score_openai(prompt)
        if result:
            return result

    if ANTHROPIC_API_KEY:
        result = _score_anthropic(prompt)
        if result:
            return result

    print("  WARNING: All LLM backends failed.")
    return None


def _parse_llm_response(text):
    """Extract and parse JSON from LLM response."""
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def _score_ollama(prompt):
    try:
        import ollama
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ]
        )
        text = response["message"]["content"]
        result = _parse_llm_response(text)
        if result:
            print(f"  [Ollama] {result}")
        return result
    except Exception as e:
        print(f"  Ollama unavailable: {e}")
        return None


def _score_openai(prompt):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.1,
            max_tokens=200
        )
        text = response.choices[0].message.content
        result = _parse_llm_response(text)
        if result:
            print(f"  [OpenAI] {result}")
        return result
    except Exception as e:
        print(f"  OpenAI error: {e}")
        return None


def _score_anthropic(prompt):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text
        result = _parse_llm_response(text)
        if result:
            print(f"  [Anthropic] {result}")
        return result
    except Exception as e:
        print(f"  Anthropic error: {e}")
        return None
