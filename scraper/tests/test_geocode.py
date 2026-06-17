# scraper/tests/test_geocode.py
from unittest.mock import MagicMock, patch

GOOD_RESULT = [{"geometry": {"location": {"lat": 47.657, "lng": -122.303}},
                "formatted_address": "Padelford Garage, Seattle, WA 98105, USA"}]

def test_returns_lat_lng_address():
    with patch("googlemaps.Client") as cls:
        cls.return_value.geocode.return_value = GOOD_RESULT
        from scraper.tools.geocode import geocode_address
        r = geocode_address("Padelford Garage", "fake-key")
    assert r["lat"] == 47.657
    assert r["lng"] == -122.303
    assert "Padelford" in r["google_address"]

def test_returns_nulls_on_empty_response():
    with patch("googlemaps.Client") as cls:
        cls.return_value.geocode.return_value = []
        from scraper.tools.geocode import geocode_address
        r = geocode_address("Nowhere", "fake-key")
    assert r == {"lat": None, "lng": None, "google_address": None}

def test_returns_nulls_on_api_exception():
    with patch("googlemaps.Client") as cls:
        cls.return_value.geocode.side_effect = Exception("quota exceeded")
        from scraper.tools.geocode import geocode_address
        r = geocode_address("Somewhere", "fake-key")
    assert r == {"lat": None, "lng": None, "google_address": None}
