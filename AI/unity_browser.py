"""Chrome lifecycle setup shared by Unity assignment and case lookup."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService


class UnityBrowserSession:
    """Own one lazy driver for All or postapproval-NCM Assign, never across runs."""

    def __init__(self):
        self.driver = None
        self.preserved = False
        self.result = None

    def acquire(self, factory):
        if self.driver is None:
            self.driver = factory()
        return self.driver

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        if self.driver is None or self.preserved:
            return False
        try:
            self.driver.quit()
        except Exception as cleanup_error:
            if error is not None:
                failure = RuntimeError(
                    f"Unity browser cleanup failed after {type(error).__name__}.")
                failure.cleanup_error = cleanup_error
                raise failure from error
            primary = ""
            if self.result and self.result["status"] != "completed":
                primary_type = (self.result.get("error") or {}).get("type") or self.result["status"]
                primary = (f" after {self.result['reason']}: "
                           f"{primary_type}")
            failure = RuntimeError("Unity browser cleanup failed" + primary)
            failure.process_result = self.result
            raise failure from cleanup_error
        return False


def create_driver(driver_path="", *, detach=False, log_output=None):
    options = ChromeOptions()
    for argument in (
        "--ignore-certificate-errors",
        "--allow-insecure-localhost",
        "--disable-popup-blocking",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--log-level=3",
        "--disable-features=OnDeviceModel,OptimizationHints,OptimizationGuideModelDownloading",
    ):
        options.add_argument(argument)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option("detach", detach)
    # An unset executable lets Selenium Manager resolve the installed Chrome driver.
    service = ChromeService(executable_path=driver_path or None, log_output=log_output)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    return driver
