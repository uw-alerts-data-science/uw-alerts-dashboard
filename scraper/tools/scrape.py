import re
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

UW_ALERTS_URL = "https://emergency.uw.edu/"
DATE_RE = re.compile(r"^[A-Za-z]+\s+\d{1,2},\s+\d{4}")


class ScrapingError(Exception):
    pass


def scrape_uw_blog() -> dict:
    try:
        resp = requests.get(UW_ALERTS_URL, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise ScrapingError(f"Failed to fetch page: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find(id="main_content")
    if not main:
        raise ScrapingError("Could not find main_content element on page")

    paragraphs = [p.get_text(separator="\n").strip() for p in main.find_all("p")]
    date_idx = next((i for i, p in enumerate(paragraphs) if DATE_RE.match(p)), None)
    if date_idx is None:
        raise ScrapingError("Could not find a date paragraph in page content")

    raw_text = "\n\n".join(paragraphs[date_idx: date_idx + 2])
    return {"raw_text": raw_text, "scraped_at": datetime.now(timezone.utc).isoformat()}
