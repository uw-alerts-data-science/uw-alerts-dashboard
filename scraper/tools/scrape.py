from datetime import datetime, timezone
import time
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


def scrape_page(page_num: int) -> list:
    """Scrape all articles from a given page of the UW alerts blog.

    Returns a list of article dicts ordered oldest-first (WordPress lists
    newest-first on the page; we reverse so callers can process chronologically).
    Each dict has keys: raw_text, article_url, scraped_at, page_num.

    An empty list means the page exists but has no dated articles (not an error).

    Args:
        page_num: 1 for the most recent page, 19 for the oldest (as of 2026).
    """
    url = UW_ALERTS_URL if page_num == 1 else f"{UW_ALERTS_URL}page/{page_num}/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise ScrapingError(f"Failed to fetch page {page_num}: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main", class_="site-main")
    if not main:
        raise ScrapingError(f"Could not find site-main element on page {page_num}")

    scraped_at = datetime.now(timezone.utc).isoformat()
    results = []

    for article in main.find_all("article"):
        if not article.find("time", class_="entry-date"):
            continue  # skip non-alert articles (nav, promo, etc.)

        # Prefer the article's own permalink over the listing page URL
        article_url = url
        title_el = article.find("h2", class_="entry-title") or article.find(
            "h1", class_="entry-title"
        )
        if title_el:
            a = title_el.find("a", href=True)
            if a:
                article_url = a["href"]

        results.append(
            {
                "raw_text": article.get_text(separator="\n", strip=True),
                "article_url": article_url,
                "scraped_at": scraped_at,
                "page_num": page_num,
            }
        )

    # WordPress lists newest-first; reverse so callers process oldest-first
    results.reverse()
    return results


def scrape_article_urls(page_num: int) -> list:
    """Fetch the listing page for page_num and return a flat list of article permalink URLs.

    Only articles that have a <time class="entry-date"> element are included;
    nav/promo articles without a date element are skipped. If a dated article
    has no title link href, that article is also skipped.

    Returns URLs in page order (WordPress lists newest-first).

    Args:
        page_num: 1 for the most recent page, N for older pages.
    """
    url = UW_ALERTS_URL if page_num == 1 else f"{UW_ALERTS_URL}page/{page_num}/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise ScrapingError(f"Failed to fetch page {page_num}: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main", class_="site-main")
    if not main:
        raise ScrapingError(f"Could not find site-main element on page {page_num}")

    urls = []
    for article in main.find_all("article"):
        if not article.find("time", class_="entry-date"):
            continue  # skip non-alert articles (nav, promo, etc.)

        title_el = article.find("h2", class_="entry-title") or article.find(
            "h1", class_="entry-title"
        )
        if not title_el:
            continue

        a = title_el.find("a", href=True)
        if not a:
            continue

        urls.append(a["href"])

    return urls


def scrape_article(url: str, max_retries: int = 3) -> dict:
    """Fetch an individual article permalink and return its text content.

    Retries up to max_retries times on 429 Too Many Requests, respecting the
    Retry-After header when present.

    Returns a dict with keys:
        raw_text:    text extracted from the <article> element
        article_url: the URL that was fetched
        scraped_at:  ISO8601 timestamp of when the article was fetched

    Raises ScrapingError on HTTP failure, missing <main class="site-main">,
    or missing <article> element.

    Args:
        url: Full permalink URL of the article to fetch.
        max_retries: Maximum number of retry attempts on 429 (default 3).
    """
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, timeout=10)
        except Exception as e:
            raise ScrapingError(f"Failed to fetch article {url}: {e}") from e

        if resp.status_code == 429:
            if attempt == max_retries:
                raise ScrapingError(
                    f"Failed to fetch article {url}: 429 Too Many Requests after {max_retries} retries"
                )
            wait = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            time.sleep(wait)
            continue

        try:
            resp.raise_for_status()
        except Exception as e:
            raise ScrapingError(f"Failed to fetch article {url}: {e}") from e

        break

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main", class_="site-main")
    if not main:
        raise ScrapingError(f"Could not find site-main element at {url}")

    article = main.find("article")
    if not article:
        raise ScrapingError(f"Could not find any article element at {url}")

    raw_text = article.get_text(separator="\n", strip=True)
    return {
        "raw_text": raw_text,
        "article_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
