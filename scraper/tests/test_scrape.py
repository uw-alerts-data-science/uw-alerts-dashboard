# scraper/tests/test_scrape.py
import pytest
import responses

GOOD_HTML = """<html><body>
<main class="site-main">
  <article>
    <h2 class="entry-title">UW Alert – Theft near HUB</h2>
    <span class="posted-on">
      <time class="entry-date published" datetime="2026-06-16T14:00:00-07:00">June 16, 2026 2:00 pm</time>
    </span>
    <div class="entry-content">
      <p>ORIGINAL POST: Theft near HUB. UWPD on scene. Sent at 2:00 pm Mon</p>
    </div>
  </article>
</main>
</body></html>"""

NO_ARTICLE_HTML = """<html><body>
<main class="site-main">
</main>
</body></html>"""

NO_DATE_HTML = """<html><body>
<main class="site-main">
  <article>
    <div class="entry-content"><p>No recent alerts to display.</p></div>
  </article>
</main>
</body></html>"""


@responses.activate
def test_returns_raw_text_and_scraped_at():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=GOOD_HTML, status=200)
    from scraper.tools.scrape import scrape_uw_blog
    result = scrape_uw_blog()
    assert "ORIGINAL POST" in result["raw_text"]
    assert "June 16, 2026" in result["raw_text"]
    assert "scraped_at" in result


@responses.activate
def test_raises_on_missing_site_main():
    responses.add(responses.GET, "https://emergency.uw.edu/", body="<html><body></body></html>", status=200)
    from scraper.tools.scrape import scrape_uw_blog, ScrapingError
    with pytest.raises(ScrapingError, match="site-main"):
        scrape_uw_blog()


@responses.activate
def test_raises_on_no_article():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=NO_ARTICLE_HTML, status=200)
    from scraper.tools.scrape import scrape_uw_blog, ScrapingError
    with pytest.raises(ScrapingError, match="article"):
        scrape_uw_blog()


@responses.activate
def test_raises_on_no_date():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=NO_DATE_HTML, status=200)
    from scraper.tools.scrape import scrape_uw_blog, ScrapingError
    with pytest.raises(ScrapingError, match="date"):
        scrape_uw_blog()


@responses.activate
def test_raises_on_network_error():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=ConnectionError("timeout"))
    from scraper.tools.scrape import scrape_uw_blog, ScrapingError
    with pytest.raises(ScrapingError):
        scrape_uw_blog()
