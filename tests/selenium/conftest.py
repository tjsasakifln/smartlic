import os
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from insight_collector import InsightCollector, get_collector

BASE_URL = os.getenv("BASE_URL", "https://smartlic.tech")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "tiago.sasaki@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def collector() -> InsightCollector:
    c = InsightCollector()
    c.metric("base_url", BASE_URL)
    return c


@pytest.fixture(scope="session")
def driver():
    opts = ChromeOptions()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,720")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=pt-BR")
    opts.add_experimental_option("prefs", {"download.prompt_for_download": False})

    drv = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=opts,
    )
    drv.implicitly_wait(10)
    drv.set_page_load_timeout(60)
    yield drv
    drv.quit()


@pytest.fixture(scope="session")
def logged_in_driver(driver, base_url, collector):
    """Driver com sessão de admin autenticada. Faz login uma única vez."""
    if not ADMIN_PASSWORD:
        pytest.skip("ADMIN_PASSWORD não configurado — pule testes autenticados")
    from pages.login_page import LoginPage
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    page = LoginPage(driver, base_url)
    login_time = page.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    collector.metric("login_success_seconds", login_time)

    # Check if MFA screen appeared after login
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'dois fatores')]"))
        )
        if ADMIN_TOTP_SECRET:
            import pyotp
            totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
            code_input = driver.find_element(
                By.CSS_SELECTOR, "input[type='text'], input[inputmode='numeric']"
            )
            code_input.clear()
            code_input.send_keys(totp.now())
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            # Wait for redirect away from /login
            WebDriverWait(driver, 30).until(
                lambda d: "/login" not in d.current_url
            )
        else:
            pytest.skip("MFA detectado mas ADMIN_TOTP_SECRET não configurado")
    except Exception:
        pass  # No MFA screen — login succeeded directly

    return driver


@pytest.fixture(autouse=True)
def _set_test_name(request):
    try:
        c = request.getfixturevalue("collector")
        c.set_test(request.node.name)
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):
    c = get_collector()
    if c:
        c.save("insights_report.json")
        c.print_summary()
