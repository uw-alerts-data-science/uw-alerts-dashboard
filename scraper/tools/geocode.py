import logging
import googlemaps

logger = logging.getLogger("scraper")
_NULL = {"lat": None, "lng": None, "google_address": None}


def geocode_address(address: str, api_key: str) -> dict:
    try:
        results = googlemaps.Client(key=api_key).geocode(f"{address}, Seattle, WA")
        if not results:
            logger.warning("geocode_no_results", extra={"address": address})
            return _NULL.copy()
        loc = results[0]["geometry"]["location"]
        return {
            "lat": loc["lat"],
            "lng": loc["lng"],
            "google_address": results[0]["formatted_address"],
        }
    except Exception as e:
        logger.error("geocode_failed", extra={"address": address, "error": str(e)})
        return _NULL.copy()
