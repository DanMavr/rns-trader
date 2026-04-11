from bs4 import BeautifulSoup
import re

def clean_html(html: str) -> str:
    """Strip HTML tags and clean whitespace. Returns plain text."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    # Remove style and script blocks
    for tag in soup(["style", "script", "head"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines()]
    lines = [l for l in lines if l]  # remove empty lines
    text = "\n".join(lines)

    # Remove the machine code suffix (e.g. UPDDDGDDDUBDGLR)
    text = re.sub(r'\n[A-Z]{10,}\s*$', '', text)

    return text.strip()


if __name__ == "__main__":
    # Quick test
    sample = "<html><body><p>Hello <b>world</b></p><p>Second line</p></body></html>"
    print(clean_html(sample))
