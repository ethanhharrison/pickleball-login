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
from datetime import timedelta, date
from calendar import month_abbr

from config import EMAIL, PASSWORD, EVENT_NAME, CVV

URL = "https://anc.apm.activecommunities.com/cityofhermosabeach/signin?onlineSiteId=0&from_original_cui=true&override_partial_error=False&custom_amount=False&params=aHR0cHM6Ly9hcG0uYWN0aXZlY29tbXVuaXRpZXMuY29tL2NpdHlvZmhlcm1vc2FiZWFjaC9BY3RpdmVOZXRfSG9tZT9GaWxlTmFtZT1vbmxpbmVxdWlja2ZhY2lsaXR5cmVzZXJ2ZS5zZGkmZnVuY3Rpb249b25saW5lcXVpY2tmYWNpbGl0eXJlc2VydmUmYXVpX2NvbG9yX3RoZW1lPXRoZW1lX2JsYWNrJmZ1bmN0aW9uX3RleHQ9VG8gT25saW5lIFF1aWNrIFJlc2VydmF0aW9uJmRheWNhcmVfbWVudV90aXRsZV9sb3dlcj1mbGV4cmVnJmFtc19vcmRlcl9kZXNjcmlwdG9yPUNpdHkgb2YgSGVybW9zYSBCZWFjaCBQYXJrcyBhbmQgUmVjIERlcHQmbXlhY2NvdW50X3JlZGVzaWduX29uX2N1aT1DaGVja2VkJnJubz0yJmFjdGl2aXR5X2xhYmVsX3VuZXNjcGFlX2pzX2FuZF9kZWNvZGVfbWFsX2NoYXI9QWN0aXZpdHkmcmVkZXNpZ25fb25fY3VpX215X2FjY291bnRfdGhyb3VnaF90ZXh0PUFjY2VzcyBNeSBBY2NvdW50JmpzX2Ftc19vcmRlcl9kZXNjcmlwdG9yPUNpdHkgb2YgSGVybW9zYSBCZWFjaCBQYXJrcyBhbmQgUmVjIERlcHQmZm9yX2N1aT1UcnVlJnNkaXJlcWF1dGg9MTcwMjc0NzkwNzYxOSZqc19jYWxlbmRhcnNfbGFiZWw9Q2FsZW5kYXJzJmFjdGl2aXRpZXNfbGFiZWxfbG93ZXJfanM9YWN0aXZpdGllcyZjdWlfY29uc3VtZXI9dHJ1ZSZnaWZ0X2NlcnRpZmljYXRlX2xhYmVsX3VuZXNjYXBlX2pzX2FuZF9kZWNvZGVfbWFsX2NoYXI9R2lmdCBDYXJkJmNhbGVuZGFyc19sYWJlbD1DYWxlbmRhcnMmZnJvbUxvZ2luUGFnZT10cnVl"

four_days_before: dict[int, schedule.Job] = {
    0: schedule.every().thursday,
    1: schedule.every().friday,
    2: schedule.every().saturday,
    3: schedule.every().sunday,
    4: schedule.every().monday,
    5: schedule.every().tuesday,
    6: schedule.every().wednesday
}

def next_weekday(weekday, d: date = date.today()):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days_ahead)

def best_available_reservation(priority_list: list[list[int]], court_one: list[int], court_two: list[int]):
    for priority in priority_list:
        if all([t in court_one for t in priority]):
            print(f"Reserving times {priority} on court #1")
            return [(1, t) for t in priority] 
        elif all([t in court_two for t in priority]):
            print(f"Reserving times {priority} on court #2")
            return [(2, t) for t in priority]
    # no times available
    print("No available times!")

def login_and_reserve(day_of_week: int, priority_list: list[tuple]):
    print("Opening website...")
    service = webdriver.ChromeService()
    driver = webdriver.Chrome(service=service)
    driver.get(URL)
    # enter email
    email_field = driver.find_element(By.XPATH, "//input[@type='text']")
    email_field.send_keys(EMAIL)

    # enter password
    password_field = driver.find_element(By.XPATH, "//input[@type='password']")
    password_field.send_keys(PASSWORD)

    # submit login info
    submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    submit_button.click()

    # choose pickleball member
    facility_select = Select(WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "facilitygroup_id"))
    ))
    facility_select.select_by_visible_text("Pickleball Member")

    # go to next thursday
    game_day = next_weekday(weekday=day_of_week)
    year_select = Select(driver.find_element(By.XPATH, "//select[@aria-label='Year']"))
    year_select.select_by_visible_text(str(game_day.year))
    month_select = Select(driver.find_element(By.XPATH, "//select[@aria-label='Month']"))
    month_select.select_by_visible_text(month_abbr[game_day.month])
    day_select = Select(driver.find_element(By.XPATH, "//select[@aria-label='Day']"))
    day_select.select_by_visible_text(str(game_day.day))

    # check availability
    check_availability_button = driver.find_element(By.XPATH, "//input[@value='Check Availability']")
    check_availability_button.click()

    # Enter event name
    event_name_field = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Event Name']"))
    )
    event_name_field.send_keys(EVENT_NAME)

    # Find the available times and get best reservation
    soup = BeautifulSoup(driver.page_source, "html.parser")
    all_inputs = soup.find_all(type="checkbox")
    court_one = []
    court_two = []
    for input in all_inputs:
        try:
            court, time = re.findall(r'\d+', input["title"])
            if int(court) == 1:
                court_one.append(int(time))
            else:
                court_two.append(int(time))
        except KeyError:
            pass
    best_times = best_available_reservation(priority_list, court_one, court_two)

    # select the boxes of the best times
    if best_times:
        for box in best_times:
            box_title = f"Pickleball Court #{box[0]} : {box[1]}pm"
            box_element = driver.find_element(By.XPATH, f"//input[@title='{box_title}']")
            box_element.click()
        return driver

def finalize_reservation(driver: webdriver.Chrome):
    # calculate charges
    calculate_button = driver.find_element(By.XPATH, "//input[@name='calccharges']")
    calculate_button.click()

    # agree to waiver
    waiver_checkbox = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Agree to Waiver']"))
    )
    waiver_checkbox.click()

    # reserve the times
    reserve_button = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//input[@name='reserve']"))
    )
    reserve_button.click()

    # add CVV
    cvv_input = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//input[@name='cvv']"))
    )
    cvv_input.send_keys(CVV)

    # I am above thirteen
    thirteen_box = driver.find_element(By.ID, "thirteen")
    thirteen_box.click()

    # Finalize!
    continue_box = driver.find_element(By.XPATH, "//input[@name='Continue']")
    continue_box.click()


def main():
    print("Activated!")
    root = tk.Tk()
    v = tk.StringVar()
    canvas1 = tk.Canvas(root, width=300, height=300)
    canvas1.pack()

    def make_reservation():
        priority = [(3, 4), (2, 3)]
        day_of_reservation = 3
        day_to_schedule = four_days_before[day_of_reservation]

        driver = day_to_schedule.at("06:58:00").do(login_and_reserve, day_of_reservation, priority)
        if driver:
            day_to_schedule.at("07:00:01").do(finalize_reservation, driver)

        while True:
            schedule.run_pending()
            time.sleep(1)
            time_of_next_run = schedule.next_run()
            time_now = datetime.now()
            time_remaining = time_of_next_run - time_now
            time_left_text = f'Time until execution: ' + str(time_remaining).split('.', 2)[0]
            v.set(time_left_text)
            print(time_left_text)
            root.update()

    button = tk.Button(text="Schedule Reservation", command=make_reservation, bg="white", fg="black")
    canvas1.create_window(150, 150, window=button)

    label = tk.Label(root, textvariable=v)
    canvas1.create_window(150, 180, window=label)

    root.mainloop()
        
if __name__ == "__main__":
    main()