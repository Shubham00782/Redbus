import logging
from playwright.sync_api import Page, Response, expect

logger = logging.getLogger(__name__)

class BasePage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def navigate(self, path: str = "") -> Response:
        """Navigates to the base URL concatenated with path."""
        url = f"{self.base_url}{path}" if path.startswith("/") or not path else f"{self.base_url}/{path}"
        logger.info(f"Navigating to URL: {url}")
        return self.page.goto(url)

    def click(self, locator: str, timeout: float = None):
        """Clicks an element specified by the locator after waiting for it."""
        logger.info(f"Clicking element: {locator}")
        self.page.locator(locator).click(timeout=timeout)

    def type_text(self, locator: str, text: str, delay: float = 0.0, timeout: float = None):
        """Types text into an input field specified by the locator."""
        logger.info(f"Typing '{text}' into element: {locator}")
        self.page.locator(locator).fill("", timeout=timeout)  # Clear first
        self.page.locator(locator).press_sequentially(text, delay=delay, timeout=timeout)

    def fill_text(self, locator: str, text: str, timeout: float = None):
        """Fills text into an input field specified by the locator (faster than type_text)."""
        logger.info(f"Filling '{text}' into element: {locator}")
        self.page.locator(locator).fill(text, timeout=timeout)

    def get_text(self, locator: str, timeout: float = None) -> str:
        """Retrieves the text content of an element."""
        text = self.page.locator(locator).text_content(timeout=timeout)
        logger.info(f"Retrieved text '{text}' from element: {locator}")
        return text or ""

    def is_visible(self, locator: str, timeout: float = None) -> bool:
        """Checks if an element is visible on the page."""
        visible = self.page.locator(locator).is_visible(timeout=timeout)
        logger.info(f"Element {locator} visibility state: {visible}")
        return visible

    def check_checkbox(self, locator: str, timeout: float = None):
        """Checks a checkbox/radio element."""
        logger.info(f"Checking element: {locator}")
        self.page.locator(locator).check(timeout=timeout)

    def wait_for_selector(self, locator: str, state: str = "visible", timeout: float = None):
        """Waits for a selector to meet a certain state ('attached', 'detached', 'visible', 'hidden')."""
        logger.info(f"Waiting for element: {locator} to be {state}")
        self.page.locator(locator).wait_for(state=state, timeout=timeout)

    def verify_title(self, title_text: str):
        """Asserts that the page title matches expected text."""
        logger.info(f"Verifying page title matches: '{title_text}'")
        expect(self.page).to_have_title(title_text)
