import logging
import re

from playwright.sync_api import expect

from locators.home_locators import HomeLocators
from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class HomePage(BasePage):
    """redBus home search: From, To, and Search buses."""

    def dismiss_app_banner(self):
        banner = self.page.locator(HomeLocators.APP_INSTALL_CLOSE)
        if banner.count() and banner.first.is_visible():
            logger.info("Closing the app install banner")
            banner.first.click()

    def search_route(self, from_city: str, to_city: str):
        """Enter the route, pick the first suggestion for each city, and search."""
        self._forget_saved_route()
        self._reveal_search_form()
        self.dismiss_app_banner()
        self._select_city(HomeLocators.FROM_INPUT, from_city)
        self._select_city(HomeLocators.TO_INPUT, to_city)
        self._click_search()
        self._dismiss_preference_sheet()

    def _reveal_search_form(self):
        """Keep the hero search form in view. Scrolling it pins a header over the inputs."""
        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.locator(HomeLocators.FROM_INPUT).wait_for(state="visible", timeout=15000)

    def _forget_saved_route(self):
        """Drop the route redBus restores into the search box.

        Typing the same city while it is still the other end hides the city
        suggestion and leaves only boarding points such as Waghala-Nanded.
        """
        self.page.evaluate(
            """() => {
                [
                    'src_name', 'dest_name', 'src_id', 'dest_id',
                    'src_locType', 'dest_locType', 'src_country', 'dest_country',
                    'src_parentCityId', 'dest_parentCityId',
                ].forEach((key) => localStorage.removeItem(key));
            }"""
        )
        self.page.reload(wait_until="commit")

    def _select_city(self, input_locator: str, city: str):
        logger.info("Selecting city '%s'", city)
        self._reveal_search_form()
        field = self.page.locator(input_locator)
        field.evaluate("el => el.focus({preventScroll: true})")
        self.page.keyboard.press("ControlOrMeta+A")
        self.page.keyboard.press("Backspace")
        self.page.keyboard.type(city, delay=80)
        option = self._city_option(city)
        expect(option).to_be_visible(timeout=10000)
        option.click()
        expect(field).to_have_value(re.compile(rf"^{re.escape(city)}$", re.IGNORECASE), timeout=8000)

    def _city_option(self, city: str):
        """City row only. Stop suggestions such as 'Pune University' also contain the name."""
        exact_name = re.compile(rf"^\s*{re.escape(city)}\s*$", re.IGNORECASE)
        return self.page.locator(".suggestion-item[class*='lineLength1']").filter(
            has_text=exact_name
        ).first

    def _click_search(self):
        self._reveal_search_form()
        logger.info("Clicking Search buses")
        buttons = self.page.locator(HomeLocators.SEARCH_BUTTON).locator("visible=true")
        buttons.last.click()

    def _dismiss_preference_sheet(self):
        """Proceed with no filters when redBus asks for boarding preferences."""
        sheet = self.page.locator(HomeLocators.PREFERENCE_SHEET)
        self.page.wait_for_selector(
            f"{HomeLocators.PREFERENCE_SHEET}, {HomeLocators.BUSES_FOUND}",
            state="visible",
            timeout=20000,
        )
        if sheet.is_visible():
            logger.info("Preference sheet is open; continuing without filters")
            sheet.locator(HomeLocators.PROCEED_BUTTON).click()
