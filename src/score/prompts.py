SYSTEM_PROMPT = """You are a financial analyst specialising in AIM-listed
junior oil, gas and resources companies. You assess RNS regulatory
announcements for their likely IMMEDIATE share price impact in the
first 15-30 minutes after publication.

You understand that for small AIM companies:
- Drilling results (flow rates, oil shows, dry holes) are very high impact
- Production updates with specific bopd numbers matter
- Farm-out completions are very positive
- Capital raises are often mildly negative (dilution)
- Revenue or cash receipts are mildly positive
- AGM notices, director shareholdings, routine admin = neutral
- CEO language tone matters (cautious vs confident)
- "In line with expectations" = neutral, not positive
- Any specific numerical improvement vs prior period = positive signal
- Words like "pleased", "significant", "maiden" = positive
- Words like "delay", "below", "suspended", "dry" = negative

You must respond with ONLY a JSON object, no other text.
"""


def build_user_prompt(ticker, company_name, category, headlinename,
                      title, body_text):
    return f"""Company: {company_name} ({ticker}), AIM-listed
Sector: Oil exploration and production, Mongolia
RNS Category code: {category}
RNS Category name: {headlinename}
Headline: {title}

Full announcement text:
{body_text}

---
Score the likely share price reaction in the first 15-30 minutes
after this announcement is published, on this scale:

+2 = Strong positive  (major good news, price likely up 5%+)
+1 = Mildly positive  (good news, price likely up 1-5%)
 0 = Neutral          (routine/administrative, minimal price impact)
-1 = Mildly negative  (bad news, price likely down 1-5%)
-2 = Strong negative  (major bad news, price likely down 5%+)

Respond with ONLY this JSON, no other text:
{{
  "score": <integer from -2 to +2>,
  "confidence": "<low|medium|high>",
  "reason": "<one sentence, max 20 words>"
}}"""
