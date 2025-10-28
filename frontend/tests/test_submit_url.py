import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless=new")  # optional for CI
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    yield driver
    driver.quit()


def test_empty_url(driver):
    driver.get("http://localhost:5173")

    submit = driver.find_element(By.ID, "submit-btn")
    submit.click()

    time.sleep(0.5)
    status = driver.find_element(By.ID, "status-text").text
    assert "Please enter a valid URL." in status


def test_invalid_url_format(driver):
    driver.get("http://localhost:5173")

    input_box = driver.find_element(By.ID, "url-input")
    submit = driver.find_element(By.ID, "submit-btn")

    input_box.send_keys("invalid_url")
    submit.click()

    time.sleep(0.5)
    status = driver.find_element(By.ID, "status-text").text
    assert "Please enter a valid URL format." in status


def test_no_server_response(driver):
    driver.get("http://localhost:5173")

    input_box = driver.find_element(By.ID, "url-input")
    submit = driver.find_element(By.ID, "submit-btn")

    input_box.send_keys("https://example.com")
    submit.click()

    time.sleep(2)
    status = driver.find_element(By.ID, "status-text").text
    assert "No response" in status or "Server error" in status


@pytest.mark.optional
def test_successful_submission(driver):
    """
    This assumes your backend (http://localhost:5000/artifacts/)
    returns a 200 response when posting { "url": "https://example.com" }.
    """
    driver.get("http://localhost:5173")

    input_box = driver.find_element(By.ID, "url-input")
    submit = driver.find_element(By.ID, "submit-btn")

    input_box.send_keys("https://example.com")
    submit.click()

    time.sleep(2)
    status = driver.find_element(By.ID, "status-text").text
    assert "✅ URL submitted successfully!" in status
