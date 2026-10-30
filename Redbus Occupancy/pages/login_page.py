import logging

from playwright.sync_api import expect

from locators.login_locators import LoginLocators
from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class LoginPage(BasePage):
    """redBus login-offers dialog that sometimes covers a bus before seats load."""

    def __init__(self, page, base_url):
        super().__init__(page, base_url)
        self.locators = LoginLocators

    def dismiss_offer_if_present(self, timeout: float = 2500) -> bool:
        """Close 'Login to get exciting offers' when it is open.

        The dialog is not always shown. Its Close control is the second
        Close button on the page; the first belongs to the seat layout.
        """
        heading = self.page.locator(self.locators.OFFER_HEADING)
        try:
            heading.first.wait_for(state="visible", timeout=timeout)
        except Exception:
            return False

        logger.info("Closing the login offers prompt")
        closes = self.page.locator(self.locators.CLOSE_BUTTON)
        visible_indexes = [
            index for index in range(closes.count()) if closes.nth(index).is_visible()
        ]
        if len(visible_indexes) >= 2:
            closes.nth(visible_indexes[1]).click()
        elif visible_indexes:
            closes.nth(visible_indexes[0]).click()
        else:
            closes.nth(1).click()
        expect(heading).to_have_count(0, timeout=5000)
        return True
