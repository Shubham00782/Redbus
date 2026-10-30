import logging
import re

from playwright.sync_api import expect

from locators.seat_locators import SeatLocators
from pages.base_page import BasePage
from pages.login_page import LoginPage

logger = logging.getLogger(__name__)

_PRICE = re.compile(r"price\s+(\d+)\s+rupees", re.IGNORECASE)


def _occupancy_percentage(booked_seats, total_seats):
    """Booked seats / total seats * 100, rounded to one decimal."""
    if not isinstance(booked_seats, int) or not isinstance(total_seats, int) or total_seats <= 0:
        return ""
    return round(booked_seats / total_seats * 100, 1)


class SeatLayoutPage(BasePage):
    """Seat map opened from a bus card."""

    def _select_seats_heading(self):
        return self.page.get_by_text(SeatLocators.SELECT_SEATS_TEXT, exact=True).locator("visible=true")

    def is_open(self) -> bool:
        return self._select_seats_heading().count() > 0

    def dismiss_login_offer_if_present(self, timeout: float = 2500) -> bool:
        return LoginPage(self.page, self.base_url).dismiss_offer_if_present(timeout)

    def wait_until_open(self):
        logger.info("Waiting for the seat layout")
        self.dismiss_login_offer_if_present()
        heading = self._select_seats_heading()
        try:
            expect(heading.first).to_be_visible(timeout=8000)
        except AssertionError:
            self.dismiss_login_offer_if_present()
            expect(heading.first).to_be_visible(timeout=15000)
        self.dismiss_login_offer_if_present(timeout=1000)
        self.page.locator(SeatLocators.SOLD_SEATS + ", " + SeatLocators.AVAILABLE_SEATS).first.wait_for(
            state="visible",
            timeout=20000,
        )

    def read_occupancy(self) -> dict:
        """Total seats, booked seats, and min/max price of vacant seats."""
        self.wait_until_open()
        total_seats = self._total_seats()
        booked = self.page.locator(SeatLocators.SOLD_SEATS).count()
        prices = self._available_prices()
        occupancy = {
            "total_seats": total_seats,
            "booked_seats": booked,
            "occupancy_percentage": _occupancy_percentage(booked, total_seats),
            "min_price": min(prices) if prices else "",
            "max_price": max(prices) if prices else "",
        }
        logger.info(
            "Total seats %s, sold %s, occupancy %s%%, vacant prices %s-%s",
            occupancy["total_seats"],
            occupancy["booked_seats"],
            occupancy["occupancy_percentage"],
            occupancy["min_price"],
            occupancy["max_price"],
        )
        return occupancy

    def _total_seats(self) -> int:
        """Seat buttons on the first deck, doubled for the matching second deck."""
        container = self.page.locator(SeatLocators.SEATS_CONTAINER).first
        container.wait_for(state="attached", timeout=15000)
        deck_count = container.locator(SeatLocators.DECK_SEAT_BUTTON).count()
        return deck_count * 2

    def close(self):
        logger.info("Closing the seat layout")
        closed = self.page.evaluate(
            """() => {
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                };
                const heading = [...document.querySelectorAll('span, div, p, h1, h2, h3')].find((el) => {
                    const ownText = [...el.childNodes]
                        .filter((node) => node.nodeType === Node.TEXT_NODE)
                        .map((node) => node.textContent)
                        .join('')
                        .trim();
                    return ownText === 'Select seats' && isVisible(el);
                });
                let node = heading;
                for (let depth = 0; depth < 12 && node; depth += 1) {
                    const button = [...node.querySelectorAll('button[aria-label="Close"]')].find(isVisible);
                    if (button) {
                        button.click();
                        return true;
                    }
                    node = node.parentElement;
                }
                return false;
            }"""
        )
        if not closed:
            buttons = self.page.locator(SeatLocators.CLOSE_BUTTON)
            for index in range(buttons.count() - 1, -1, -1):
                button = buttons.nth(index)
                if button.is_visible():
                    button.click()
                    closed = True
                    break
        if not closed:
            raise TimeoutError("Seat layout Close button was not visible")
        expect(self._select_seats_heading()).to_have_count(0, timeout=15000)

    def _available_prices(self) -> list:
        seats = self.page.locator(SeatLocators.AVAILABLE_SEATS)
        prices = []
        for index in range(seats.count()):
            label = seats.nth(index).get_attribute("aria-label") or ""
            match = _PRICE.search(label)
            if match:
                prices.append(int(match.group(1)))
        return prices
