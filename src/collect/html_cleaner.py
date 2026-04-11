import re
from bs4 import BeautifulSoup


def clean_html(html: str) -> str:
    """
    Strip HTML tags, remove inline CSS/JS, clean whitespace.
    Returns plain text suitable for LLM input.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags
    for tag in soup(["style", "script", "head", "img"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Clean up lines
    lines = [line.strip() for line in text.splitlines()]
    lines = [l for l in lines if l]
    text = "\n".join(lines)

    # Remove machine-code suffix appended by RNS (e.g. "UPDDDGDDDUBDGLR")
    text = re.sub(r'\n[A-Z]{8,}\s*$', "", text)

    return text.strip()


if __name__ == "__main__":
    sample = "<html><body><p>Hello <b>world</b></p><p>Second para</p></body></html>"
    print(clean_html(sample))
