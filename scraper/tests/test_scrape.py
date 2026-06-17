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

MULTI_ARTICLE_HTML = """<html><body>
<main class="site-main">
  <article>
    <h2 class="entry-title"><a href="https://emergency.uw.edu/2024/alert-2/">Alert 2 (newer)</a></h2>
    <time class="entry-date published" datetime="2024-03-02T10:00:00-08:00">March 2, 2024</time>
    <div class="entry-content"><p>ORIGINAL POST: Robbery near Kane Hall.</p></div>
  </article>
  <article>
    <h2 class="entry-title"><a href="https://emergency.uw.edu/2024/alert-1/">Alert 1 (older)</a></h2>
    <time class="entry-date published" datetime="2024-03-01T09:00:00-08:00">March 1, 2024</time>
    <div class="entry-content"><p>ORIGINAL POST: Theft near Red Square.</p></div>
  </article>
  <article>
    <div class="entry-content"><p>No date — should be skipped.</p></div>
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


# ── scrape_page() tests ──────────────────────────────────────────────────────

@responses.activate
def test_scrape_page_1_uses_base_url():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=GOOD_HTML, status=200)
    from scraper.tools.scrape import scrape_page
    results = scrape_page(1)
    assert len(results) == 1
    assert "ORIGINAL POST" in results[0]["raw_text"]
    assert results[0]["page_num"] == 1


@responses.activate
def test_scrape_page_n_uses_paged_url():
    responses.add(responses.GET, "https://emergency.uw.edu/page/5/", body=GOOD_HTML, status=200)
    from scraper.tools.scrape import scrape_page
    results = scrape_page(5)
    assert len(results) == 1
    assert results[0]["page_num"] == 5


@responses.activate
def test_scrape_page_returns_multiple_articles():
    responses.add(responses.GET, "https://emergency.uw.edu/page/3/", body=MULTI_ARTICLE_HTML, status=200)
    from scraper.tools.scrape import scrape_page
    results = scrape_page(3)
    # Two dated articles; one without date is skipped
    assert len(results) == 2


@responses.activate
def test_scrape_page_reversed_oldest_first():
    """WordPress lists newest-first; scrape_page should reverse to oldest-first."""
    responses.add(responses.GET, "https://emergency.uw.edu/page/3/", body=MULTI_ARTICLE_HTML, status=200)
    from scraper.tools.scrape import scrape_page
    results = scrape_page(3)
    assert "Red Square" in results[0]["raw_text"]   # older article first
    assert "Kane Hall" in results[1]["raw_text"]    # newer article second


@responses.activate
def test_scrape_page_extracts_permalink():
    responses.add(responses.GET, "https://emergency.uw.edu/page/3/", body=MULTI_ARTICLE_HTML, status=200)
    from scraper.tools.scrape import scrape_page
    results = scrape_page(3)
    assert results[0]["article_url"] == "https://emergency.uw.edu/2024/alert-1/"
    assert results[1]["article_url"] == "https://emergency.uw.edu/2024/alert-2/"


@responses.activate
def test_scrape_page_skips_articles_without_date():
    responses.add(responses.GET, "https://emergency.uw.edu/page/3/", body=MULTI_ARTICLE_HTML, status=200)
    from scraper.tools.scrape import scrape_page
    results = scrape_page(3)
    for r in results:
        assert "No date" not in r["raw_text"]


@responses.activate
def test_scrape_page_empty_list_when_no_dated_articles():
    responses.add(responses.GET, "https://emergency.uw.edu/page/2/", body=NO_DATE_HTML, status=200)
    from scraper.tools.scrape import scrape_page
    results = scrape_page(2)
    assert results == []


@responses.activate
def test_scrape_page_raises_on_missing_site_main():
    responses.add(responses.GET, "https://emergency.uw.edu/page/2/", body="<html><body></body></html>", status=200)
    from scraper.tools.scrape import scrape_page, ScrapingError
    with pytest.raises(ScrapingError, match="site-main"):
        scrape_page(2)


@responses.activate
def test_scrape_page_raises_on_network_error():
    responses.add(responses.GET, "https://emergency.uw.edu/page/2/", body=ConnectionError("timeout"))
    from scraper.tools.scrape import scrape_page, ScrapingError
    with pytest.raises(ScrapingError):
        scrape_page(2)


# ── scrape_article_urls() and scrape_article() tests ─────────────────────────

LISTING_HTML = """
<html><body>
<main class="site-main">
  <article>
    <h2 class="entry-title"><a href="https://emergency.uw.edu/2024/01/theft/">Theft</a></h2>
    <time class="entry-date">Jan 1 2024</time>
  </article>
  <article>
    <h2 class="entry-title"><a href="https://emergency.uw.edu/2024/02/assault/">Assault</a></h2>
    <time class="entry-date">Feb 1 2024</time>
  </article>
  <article>
    <!-- no time element — should be skipped -->
    <h2 class="entry-title"><a href="https://emergency.uw.edu/promo/">Promo</a></h2>
  </article>
</main>
</body></html>
"""

ARTICLE_HTML = """
<html><body>
<main class="site-main">
  <article>
    <time class="entry-date">Jan 1 2024</time>
    <div class="entry-content">Theft occurred near HUB at 10pm. UWPD responding.</div>
  </article>
</main>
</body></html>
"""


@responses.activate
def test_scrape_article_urls_returns_permalinks():
    responses.add(responses.GET, "https://emergency.uw.edu/page/3/", body=LISTING_HTML, status=200)
    from scraper.tools.scrape import scrape_article_urls
    result = scrape_article_urls(3)
    assert result == [
        "https://emergency.uw.edu/2024/01/theft/",
        "https://emergency.uw.edu/2024/02/assault/",
    ]


@responses.activate
def test_scrape_article_urls_page1_uses_base_url():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=LISTING_HTML, status=200)
    from scraper.tools.scrape import scrape_article_urls
    scrape_article_urls(1)
    assert responses.calls[0].request.url == "https://emergency.uw.edu/"


@responses.activate
def test_scrape_article_urls_raises_on_http_error():
    responses.add(responses.GET, "https://emergency.uw.edu/", body=Exception("timeout"))
    from scraper.tools.scrape import scrape_article_urls, ScrapingError
    with pytest.raises(ScrapingError):
        scrape_article_urls(1)


@responses.activate
def test_scrape_article_returns_raw_text():
    url = "https://emergency.uw.edu/2024/01/theft/"
    responses.add(responses.GET, url, body=ARTICLE_HTML, status=200)
    from scraper.tools.scrape import scrape_article
    result = scrape_article(url)
    assert "Theft occurred near HUB" in result["raw_text"]
    assert result["article_url"] == url
    assert "scraped_at" in result


@responses.activate
def test_scrape_article_raises_on_missing_article_element():
    url = "https://emergency.uw.edu/2024/01/theft/"
    no_article_html = "<html><body><main class=\"site-main\"></main></body></html>"
    responses.add(responses.GET, url, body=no_article_html, status=200)
    from scraper.tools.scrape import scrape_article, ScrapingError
    with pytest.raises(ScrapingError):
        scrape_article(url)
