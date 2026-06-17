from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

UW_ALERTS_URL = "https://emergency.uw.edu/"


class ScrapingError(Exception):
    pass


def scrape_uw_blog() -> dict:
    try:
        resp = requests.get(UW_ALERTS_URL, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise ScrapingError(f"Failed to fetch page: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main", class_="site-main")
    if not main:
        raise ScrapingError("Could not find site-main element on page")

    article = main.find("article")
    if not article:
        raise ScrapingError("Could not find any article element on page")

    time_el = article.find("time", class_="entry-date")
    if not time_el:
        raise ScrapingError("Could not find a date element in article")

    raw_text = article.get_text(separator="\n", strip=True)
    return {"raw_text": raw_text, "scraped_at": datetime.now(timezone.utc).isoformat()}
