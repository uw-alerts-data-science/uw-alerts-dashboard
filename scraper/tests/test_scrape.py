# scraper/tests/test_scrape.py
import pytest
import responses

GOOD_HTML = """<html><body><div id="main_content">
  <p>June 16, 2026</p>
  <p>ORIGINAL POST: Theft near HUB. UWPD on scene. Sent at 2:00 pm Mon</p>
</div></body></html>"""

NO_DATE_HTML = """<html><body><div id="main_content">
  <p>No recent alerts to display.</p>
</div></body></html>"""

@responses.activate
def test_returns_raw_text_and_scraped_at():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=GOOD_HTML, status=200)
    from scraper.tools.scrape import scrape_uw_blog
    result = scrape_uw_blog()
    assert "ORIGINAL POST" in result["raw_text"]
    assert "June 16, 2026" in result["raw_text"]
    assert "scraped_at" in result

@responses.activate
def test_raises_on_missing_main_content():
    responses.add(responses.GET, "https://emergency.uw.edu/", body="<html><body></body></html>", status=200)
    from scraper.tools.scrape import scrape_uw_blog, ScrapingError
    with pytest.raises(ScrapingError, match="main_content"):
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
