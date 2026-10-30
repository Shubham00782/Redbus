import logging
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pytest

from pages.home_page import HomePage
from pages.search_results_page import SearchResultsPage
from pages.seat_layout_page import SeatLayoutPage
from utils.config_reader import ConfigReader
from utils.google_sheet import GoogleSheetWriter

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_PAUSE_SECONDS = 2

_EMPTY_CARD = {
    "number_plate": "",
    "travels_name": "",
    "make": "",
    "rating": "",
    "boarding_time": "",
    "dropping_time": "",
}
_EMPTY_OCCUPANCY = {
    "total_seats": "",
    "booked_seats": "",
    "occupancy_percentage": "",
    "min_price": "",
    "max_price": "",
}


def _retry(action, description):
    """Run action up to RETRY_ATTEMPTS times. The last error is re-raised."""
    last_error = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            logger.warning(
                "%s failed on attempt %s/%s: %s",
                description,
                attempt,
                RETRY_ATTEMPTS,
                exc,
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_PAUSE_SECONDS)
    raise last_error


def _journey_date(page) -> str:
    query = parse_qs(urlparse(page.url).query)
    values = query.get("doj") or []
    return values[0] if values else ""


@pytest.mark.flaky(reruns=0)
class TestRouteOccupancy:
    """Collect both directions of the configured route and append each to its own sheet tab.

    Retries live in this class. pytest-rerunfailures is disabled for the class
    so a completed sheet write is not duplicated.
    """

    @pytest.mark.smoke
    def test_collect_route_occupancy(self, page):
        base_url = ConfigReader.read_config("Environment", "base_url")
        from_city = ConfigReader.read_config("Route", "from_city")
        to_city = ConfigReader.read_config("Route", "to_city")
        spreadsheet_id = ConfigReader.read_config("GoogleSheets", "spreadsheet_id")
        credentials_path = ConfigReader.read_config("GoogleSheets", "credentials_path")
        page.set_default_timeout(30000)

        self._collect_direction(
            page,
            base_url,
            from_city,
            to_city,
            spreadsheet_id,
            ConfigReader.read_config("GoogleSheets", "worksheet_name"),
            credentials_path,
        )
        self._collect_direction(
            page,
            base_url,
            to_city,
            from_city,
            spreadsheet_id,
            ConfigReader.read_config("GoogleSheets", "return_worksheet_name"),
            credentials_path,
        )

    def _collect_direction(
        self,
        page,
        base_url,
        from_city,
        to_city,
        spreadsheet_id,
        worksheet_name,
        credentials_path,
    ):
        logger.info("Collecting %s to %s", from_city, to_city)
        results, bus_count = _retry(
            lambda: self._search(page, base_url, from_city, to_city),
            f"Route search {from_city} to {to_city}",
        )
        journey_date = _journey_date(page)
        loaded = results.wait_for_all_buses(bus_count)
        scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        seat_layout = SeatLayoutPage(page, base_url)

        rows = []
        for index in range(loaded):
            card, occupancy = self._collect_bus(results, seat_layout, index)
            rows.append([
                scraped_at,
                journey_date,
                from_city,
                to_city,
                bus_count,
                card["number_plate"],
                card["travels_name"],
                card["make"],
                card["rating"],
                card["boarding_time"],
                card["dropping_time"],
                occupancy["total_seats"],
                occupancy["booked_seats"],
                occupancy["occupancy_percentage"],
                occupancy["min_price"],
                occupancy["max_price"],
            ])

        writer = GoogleSheetWriter(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            credentials_path=credentials_path,
        )
        writer.append_rows(rows)
        logger.info(
            "Wrote %s buses for %s to %s on %s into '%s'",
            len(rows),
            from_city,
            to_city,
            journey_date,
            worksheet_name,
        )

    def _search(self, page, base_url, from_city, to_city):
        logger.info("Opening %s", base_url)
        page.goto(base_url, wait_until="domcontentloaded")
        HomePage(page, base_url).search_route(from_city, to_city)
        results = SearchResultsPage(page, base_url)
        return results, results.get_bus_count()

    def _collect_bus(self, results, seat_layout, index):
        try:
            return _retry(
                lambda: self._read_bus(results, seat_layout, index),
                f"Bus {index + 1} seat layout",
            )
        except Exception:
            logger.exception("Bus %s failed after retries; seat fields will be blank", index + 1)
            try:
                if seat_layout.is_open():
                    seat_layout.close()
            except Exception:
                logger.exception("Could not close the seat layout after a failed bus")
            try:
                card = results.read_card(index)
            except Exception:
                logger.exception("Could not read the bus card after a failed seat layout")
                card = dict(_EMPTY_CARD)
            return card, dict(_EMPTY_OCCUPANCY)

    @staticmethod
    def _read_bus(results, seat_layout, index):
        if seat_layout.is_open():
            seat_layout.close()
        card = results.read_card(index)
        results.open_view_seats(index)
        occupancy = seat_layout.read_occupancy()
        seat_layout.close()
        return card, occupancy
