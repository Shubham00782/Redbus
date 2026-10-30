import pytest
import allure
from pathlib import Path
from playwright.sync_api import sync_playwright
import logging
import argparse
import time
from utils.config_reader import ConfigReader
from datetime import datetime

"""
---------------------------------------------------------
Pytest + Playwright Test Configuration File
---------------------------------------------------------
This file provides:
1. Command-line options
2. Hooks to track test results
3. Fixtures for browser setup and teardown
4. Screenshot, Video and trace attachment to allure reports
"""

# STEP 1: Add Command Line Options
def pytest_addoption(parser):
    """
    Adds command line options to test configuration.
    You can override these when running pytest or store defaults in pytest.ini
    """

    try:
        parser.addoption("--browser", action="store", default="chrome", help="Browser to use: chromium, firefox, webkit")
    except (ValueError, argparse.ArgumentError):
        pass
    try:
        parser.addoption("--headed", action="store", default="true", help="Whether to use headed browser")
    except (ValueError, argparse.ArgumentError):
        pass
    try:
        parser.addoption("--video", action="store", default="retain-on-failure", help="Record Video: on, off, retain-on-failure")
    except (ValueError, argparse.ArgumentError):
        pass
    try:
        parser.addoption("--screenshot", default="only-on-failure", help="Take Screenshot: on, off, only-on-failure")
    except (ValueError, argparse.ArgumentError):
        pass
    try:
        parser.addoption("--tracing", default="retain-on-failure", help="Tracing: on, off, retain-on-failure")
    except (ValueError, argparse.ArgumentError):
        pass

# STEP 2: Get Configuration Value
def get_config_value(config, option_name):
    """
    Tries to get value from command line first, otherwise from pytest.ini

    """
    # Try command-line first
    cmd_value = config.getoption(option_name)
    if cmd_value is not None:
        return cmd_value

    # Fallback to pytest.ini
    if option_name == "headed":
        ini_value = config.getini(option_name)
        return ini_value.lower() == "true" if isinstance(ini_value, str) else ini_value
    else:
        return config.getini(option_name)

def _headed_enabled(value):
    """True when the browser should show a window. Accepts bools and 'true'/'false'."""
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)

# STEP 3: HOOK to track test results (PASS/FAIL)
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    """
    Capture the test result (pass/fail/skipped) after each test.
    This is used later to decide whether to take screenshots or save traces.
    """
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)

# STEP 4: FIXTURE 1 - BROWSER CONTEXT SETUP
@pytest.fixture(scope="function")
def browser_context(request):
    """
    Creates and manages the playwright browser context.
    - Reads configuration (browser, headed mode, video settings, etc.)
    - Starts the playwright browser.
    - Enables video recording if configured.
    - cleans up automatically after each test.
    :param request:
    :return:
    """

    # Reads configuration values
    browser_name = get_config_value(request.config, "browser")
    headed_flag = get_config_value(request.config, "headed")
    video_option = get_config_value(request.config, "video")

    if isinstance(browser_name, list):
        browser_name = browser_name[0]

    b_name_lower = browser_name.lower()
    headless = not _headed_enabled(headed_flag)
    logging.info(f"Starting browser context {browser_name}")
    logging.info(f"Headless: {headless}")

    # Start Playwright
    playwright = sync_playwright().start()

    # Launch the specified browser. GitHub-hosted runners hit
    # net::ERR_HTTP2_PROTOCOL_ERROR on redBus unless Chromium uses HTTP/1.1.
    launch_options = {"headless": headless}
    if b_name_lower == "chromium" or b_name_lower == "chrome":
        launch_options["args"] = ["--disable-http2"]
        if headless:
            launch_options["args"].extend(["--no-sandbox", "--disable-dev-shm-usage"])
        browser = playwright.chromium.launch(**launch_options)
    elif b_name_lower == "firefox":
        browser = playwright.firefox.launch(**launch_options)
    elif b_name_lower == "webkit":
        browser = playwright.webkit.launch(**launch_options)
    else:
        raise ValueError(f"Unknown browser type: {browser_name}")

    # Create a browser context (optionally with video recording)
    context_options = {"viewport": {"width": 1440, "height": 900}}
    if video_option in ["on", "retain-on-failure"]:
        Path("reports/videos").mkdir(parents=True, exist_ok=True)
        context_options["record_video_dir"] = "reports/videos"
    context = browser.new_context(**context_options)

    # Yield the context for use in tests
    yield context

    # Clean up after the tests
    logging.info("Closing the browser context and stopping the Playwright....")
    context.close()
    browser.close()
    playwright.stop()

# STEP 5: FIXTURE 2 - PAGE CREATION AND TEST ARTIFACTS MANAGEMENT
@pytest.fixture(scope="function")
def page(request, browser_context):
    """
    Creates a new browser page for each test.
    - Navigates to the base URL.
    - Captures screenshots, traces and videos for failed tests. (if enabled)
    - Attach all artifacts to allure reports.
    """
    # Read test configuration
    base_url = ConfigReader.read_config("Environment", "base_url")
    screenshot_option = get_config_value(request.config, "screenshot")
    tracing_option = get_config_value(request.config, "tracing")
    video_option = get_config_value(request.config, "video")

    logging.info(f"Navigating to: {base_url}")

    # Start tracing if enabled
    if tracing_option in ["on", "retain-on-failure"]:
        logging.info("Tracing enabled - capturing screenshots and actions")
        browser_context.tracing.start(screenshots=True, snapshots=True, sources=True)

    # Creates and navigate to base URL. The HTTP/2 failure is intermittent on Actions.
    page = browser_context.new_page()
    last_error = None
    for attempt in range(1, 4):
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            logging.warning("Opening %s failed on attempt %s/3: %s", base_url, attempt, exc)
            if attempt < 3:
                time.sleep(2)
    if last_error is not None:
        raise last_error

    # Yield the page to the test
    yield page

    # After completion of test we have to manage the artifacts (screenshots, video, traces)
    test_name = request.node.name
    test_failed = hasattr(request.node, "rep_call") and request.node.rep_call.failed

    logging.info(f"Test name: {test_name}, result: {'Failed' if test_failed else 'Passed'}")

    # Save and attach trace
    if tracing_option in ["on", "retain-on-failure"]:
        Path("reports/traces").mkdir(parents=True, exist_ok=True)
        trace_path = f"reports/traces/{test_name}_trace.zip"
        browser_context.tracing.stop(path=trace_path)
        logging.info(f"Trace Saved: {trace_path}")

    # We cannot attach zip file to allure report we have to manage that in CI/CD

    # Take Screenshots if test failed
    if test_failed and screenshot_option in ["on", "only-on-failure"]:
        Path("reports/screenshots").mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = (
            f"reports/screenshots/"
            f"{test_name}_{timestamp}.png"
        )
        page.screenshot(path=screenshot_path)
        logging.info(f"Screenshot saved: {screenshot_path}")

        # Attach to allure report
        allure.attach.file(
            screenshot_path,
            name=f"{test_name}_screenshot",
            attachment_type=allure.attachment_type.PNG
        )
        logging.info(f"Screenshot attached to allure: {screenshot_path}")

    # Attach video, if available and test failed
    if test_failed and video_option in ["on", "retain-on-failure"]:
        video_path = page.video.path() if page.video else None
        if video_path and Path(video_path).exists():
            allure.attach.file(
                video_path,
                name=f"{test_name}_video",
                attachment_type=allure.attachment_type.WEBM
            )
            logging.info("Video attached to allure report}")


# STEP 6: FIXTURE 3 - API REQUEST CONTEXT
@pytest.fixture(scope="function")
def api_context(request):
    """
    Creates a Playwright APIRequestContext pre-configured with the API base URL.

    Usage (inside a test):
        def test_something(self, api_context):
            response = api_context.get("/booking")

    The base URL is read from config.ini [API] > base_url_api so that
    individual tests only need to pass the path, not the full URL.

    The context is automatically disposed after every test.
    """
    base_url_api = ConfigReader.read_config("API", "base_url_api")
    logging.info(f"Creating API context with base URL: {base_url_api}")

    playwright = sync_playwright().start()

    # Create an API request context (no browser needed)
    # ignore_https_errors=True handles corporate proxies / self-signed certs
    context = playwright.request.new_context(
        base_url=base_url_api,
        ignore_https_errors=True,
        extra_http_headers={"Content-Type": "application/json", "Accept": "application/json"}
    )

    yield context

    # Dispose the context and stop playwright after each test
    logging.info("Disposing API context and stopping Playwright...")
    context.dispose()
    playwright.stop()
