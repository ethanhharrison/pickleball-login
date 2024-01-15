from datetime import datetime
import html
import re
import time
import schedule
import tkinter as tk
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.webdriver import WebDriver
from datetime import timedelta, date
from calendar import month_abbr

from config import EMAIL, PASSWORD, EVENT_NAME, CVV

URL = "https://anc.apm.activecommunities.com/cityofhermosabeach/signin?onlineSiteId=0&from_original_cui=true&override_partial_error=False&custom_amount=False&params=aHR0cHM6Ly9hcG0uYWN0aXZlY29tbXVuaXRpZXMuY29tL2NpdHlvZmhlcm1vc2FiZWFjaC9BY3RpdmVOZXRfSG9tZT9GaWxlTmFtZT1hY2NvdW50b3B0aW9ucy5zZGkmZnJvbUxvZ2luUGFnZT10cnVl"

four_days_before: dict[int, schedule.Job] = {
    0: schedule.every().thursday,
    1: schedule.every().friday,
    2: schedule.every().saturday,
    3: schedule.every().sunday,
    4: schedule.every().monday,
    5: schedule.every().tuesday,
    6: schedule.every().wednesday,
}


def next_weekday(weekday, d: date = date.today()):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days_ahead)


def best_available_reservation(
    priority_list: list[list[int]], court_one: list[int], court_two: list[int]
) -> tuple[int, list[int]]:
    for priority in priority_list:
        if all([t in court_one for t in priority]):
            print(f"Reserving times {priority} on court #1")
            return 1, priority
        elif all([t in court_two for t in priority]):
            print(f"Reserving times {priority} on court #2")
            return 2, priority
    # no times available
    print("No available times!")


def open_website() -> WebDriver:
    print("Opening website...")
    service = webdriver.ChromeService()
    driver = webdriver.Chrome(service=service)
    driver.get(URL)
    return driver


def login(driver: WebDriver):
    # enter email
    email_field = driver.find_element(By.XPATH, "//input[@type='text']")
    email_field.send_keys(EMAIL)
    # enter password
    password_field = driver.find_element(By.XPATH, "//input[@type='password']")
    password_field.send_keys(PASSWORD)
    # submit login info
    submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    submit_button.click()


def reserve(driver: WebDriver, day_of_week: int, priority_list: list[tuple]):
    # click reservations button
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//span[text()='Reservations']"))
    ).click()
    # click pickleball button
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.XPATH, "//a[@aria-label='Pickleball Member']")
        )
    ).click()
    # Enter event name
    event_name_field = WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located(
            (By.XPATH, "//input[@aria-label='Event name']")
        )
    )
    event_name_field.click()
    event_name_field.send_keys(EVENT_NAME)
    # go to game day
    game_day = next_weekday(day_of_week)
    driver.find_element(
        By.XPATH, "//input[@aria-label='Date picker, current date']"
    ).click()
    selected_month = driver.find_element(
        By.XPATH,
        "//span[@class='an-calendar-header-title an-calendar-header-title--disabled']",
    ).text
    if selected_month != game_day.strftime("%b %Y"):
        driver.find_element(
            By.XPATH, "//i[@aria-label='Switch calendar to next month right arrow']"
        ).click()
    driver.find_element(
        By.XPATH,
        f"//div[text()='{game_day.day}']",
    ).click()
    # Find the available times and get best reservation
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    available_cells = soup.find_all(class_="grid-cell")
    court_times = {1: [], 2: []}
    for cell in available_cells:
        aria_label = cell.get("aria-label")
        if "Available" in aria_label:
            court, start, end = list(
                filter(lambda x: x > 0, map(int, re.findall(r"\d+", aria_label)))
            )
            court_times[court].append(start)
    court_and_times = best_available_reservation(
        priority_list, court_times[1], court_times[2]
    )

    if not court_and_times:
        return False

    court_number, times = court_and_times

    # select the boxes of the best times
    def time_string(t):
        if t >= 9 and t < 12:
            return f"{t}:00 AM"
        else:
            return f"{t}:00 PM"

    if times:
        for t in times:
            box_label = f"Pickleball Court #{court_number} {time_string(t)} - {time_string(t+1)} Available"
            box_element = driver.find_element(
                By.XPATH, f"//div[@aria-label='{box_label}']"
            )
            box_element.click()

    return True


def finalize(driver: webdriver.Chrome):
    # Confirm
    driver.find_element(
        By.XPATH, "//button[@data-qa-id='quick-reservation-ok-button']"
    ).click()
    # Fill waiver
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//input[@data-qa-id='shared-waiver-section-waiver-attachmentCheckbox']",
            )
        )
    ).click()
    driver.find_element(
        By.XPATH,
        "//button[.//span[text()='Save']]",
    ).click()
    # Reserve
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//button[@data-qa-id='quick-reservation-reserve-button']",
            )
        )
    ).click()
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//button[.//span[text()='OK']]",
            )
        )
    ).click()
    time.sleep(1)
    # fill CVV
    cvv_input = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//input[@name='cvv']",
            )
        )
    )
    cvv_input.click()
    cvv_input.send_keys(CVV)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//button[.//span[text()='Pay']]",
            )
        )
    ).click()


def full_reservation(day_of_week, priority_list):
    driver = open_website()
    login(driver)
    time.sleep(2)
    successful = reserve(driver, day_of_week, priority_list)
    if successful:
        finalize(driver)

    while True:
        pass


def main():
    priority = [[3, 4], [2, 3]]
    day_of_reservation = 4
    day_to_schedule = four_days_before[day_of_reservation]

    day_to_schedule.at("08:20:00").do(full_reservation, day_of_reservation, priority)

    while True:
        schedule.run_pending()
        time.sleep(1)
        time_of_next_run = schedule.next_run()
        time_now = datetime.now()
        time_remaining = time_of_next_run - time_now
        time_left_text = (
            f"Time until execution: " + str(time_remaining).split(".", 2)[0]
        )
        print(time_left_text)


if __name__ == "__main__":
    main()
