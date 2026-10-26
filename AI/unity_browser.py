"""Chrome lifecycle setup shared by Unity assignment and case lookup."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService


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
