import logging
import re

from locators.results_locators import ResultsLocators
from pages.base_page import BasePage

logger = logging.getLogger(__name__)

_RATING_VALUE = re.compile(r"([\d.]+)\s*stars", re.IGNORECASE)
_BUS_COUNT = re.compile(r"(\d+)")


class SearchResultsPage(BasePage):
    """Bus search results list for a route."""

    def bus_cards(self):
        return self.page.locator(ResultsLocators.BUS_CARD)

    def get_bus_count(self) -> int:
        """Parse the visible 'N buses found' label as an integer."""
        label = self.page.locator(ResultsLocators.BUSES_FOUND).first
        label.wait_for(state="visible", timeout=20000)
        text = (label.inner_text() or "").strip()
        match = _BUS_COUNT.search(text)
        if not match:
            raise ValueError(f"Could not parse bus count from {text!r}")
        count = int(match.group(1))
        logger.info("Buses found: %s", count)
        return count

    def wait_for_all_buses(self, expected_count: int) -> int:
        """Scroll until every result card is in the list, or loading stops."""
        last_count = -1
        stable_passes = 0
        for _ in range(30):
            count = self.bus_cards().count()
            if count >= expected_count:
                logger.info("Loaded %s bus cards", count)
                return count
            if count == last_count:
                stable_passes += 1
                if stable_passes >= 3:
                    break
            else:
                stable_passes = 0
            last_count = count
            if count:
                self.bus_cards().nth(count - 1).evaluate(
                    "el => el.scrollIntoView({block: 'center'})"
                )
            self.page.mouse.wheel(0, 2500)
            self.page.wait_for_timeout(400)
        found = self.bus_cards().count()
        logger.warning("Loaded %s of %s bus cards", found, expected_count)
        return found

    def read_card(self, index: int) -> dict:
        card = self.bus_cards().nth(index)
        card.evaluate("el => el.scrollIntoView({block: 'center'})")
        details = {
            "number_plate": self._text(card, ResultsLocators.NUMBER_PLATE),
            "travels_name": self._text(card, ResultsLocators.TRAVELS_NAME),
            "make": self._text(card, ResultsLocators.BUS_TYPE),
            "rating": self._rating(card),
            "boarding_time": self._text(card, ResultsLocators.BOARDING_TIME),
            "dropping_time": self._text(card, ResultsLocators.DROPPING_TIME),
        }
        logger.info(
            "Bus %s: %s / %s",
            index + 1,
            details["number_plate"],
            details["travels_name"],
        )
        return details

    def open_view_seats(self, index: int):
        card = self.bus_cards().nth(index)
        card.evaluate("el => el.scrollIntoView({block: 'center'})")
        logger.info("Opening seat layout for bus %s", index + 1)
        card.locator(ResultsLocators.VIEW_SEATS).click()

    @staticmethod
    def _text(card, selector: str) -> str:
        locator = card.locator(selector)
        if locator.count() == 0:
            return ""
        return (locator.first.inner_text() or "").strip()

    @staticmethod
    def _rating(card) -> str:
        rating = card.locator(ResultsLocators.RATING)
        if rating.count():
            text = (rating.first.inner_text() or "").strip()
            if text:
                return text
        chip = card.locator(ResultsLocators.RATING_CHIP)
        if chip.count() == 0:
            return ""
        label = chip.first.get_attribute("aria-label") or ""
        match = _RATING_VALUE.search(label)
        return match.group(1) if match else ""
