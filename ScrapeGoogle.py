import sqlite3
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# === DATABASE FUNCTIONS ===

DB_PATH = "RestaurantsReviews.db"

def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            url TEXT UNIQUE,
            rating REAL,
            review_count INTEGER,
            city TEXT
        )
    """)
    conn.commit()
    return conn, cursor


def insert_restaurant(cursor, name, url, rating, review_count, city):
    cursor.execute("""
        INSERT OR IGNORE INTO restaurants (name, url, rating, review_count, city)
        VALUES (?, ?, ?, ?, ?)
    """, (name, url, rating, review_count, city))


# === SELENIUM FUNCTIONS ===

def start_driver():
    options = Options()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)

def search_google_maps(driver, query="מסעדות בבאר שבע"):
    driver.get("https://www.google.com/maps")
    time.sleep(3)
    search_box = driver.find_element(By.ID, "searchboxinput")
    search_box.send_keys(query)
    search_box.send_keys(Keys.ENTER)
    time.sleep(5)

def scroll_to_end(driver, timeout=60):
    scrollable_div = driver.find_element(By.XPATH, '//div[@role="feed"]')
    last_height = driver.execute_script('return arguments[0].scrollHeight', scrollable_div)
    start_time = time.time()

    while True:
        driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
        time.sleep(2)

        new_height = driver.execute_script('return arguments[0].scrollHeight', scrollable_div)

        # Check if scroll height hasn't changed
        if new_height == last_height:
            print("Reached end of scroll.")
            break

        # Timeout safety
        if time.time() - start_time > timeout:
            print("Scroll timeout reached.")
            break

        last_height = new_height

def extract_city_from_query(query: str) -> str:
    match = re.search(r"מסעדות ב(.+)", query)
    return match.group(1).strip() if match else "לא ידוע"


def extract_restaurants(driver, city):
    containers = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK.THOPZb.CpccDe")
    restaurant_data = []

    for container in containers:
        try:
            name = container.find_element(By.CLASS_NAME, "qBF1Pd").text
            url = container.find_element(By.TAG_NAME, "a").get_attribute("href")

            # Rating and review count
            try:
                label = container.find_element(By.CLASS_NAME, "ZkP5Je").get_attribute("aria-label")
                label_clean = re.sub(r'[\u200e\u200f]', '', label)
                rating_match = re.search(r'([\d.]+)\s*כוכבים', label_clean)
                reviews_match = re.search(r'([\d,]+)\s*ביקורות', label_clean)

                rating = float(rating_match.group(1)) if rating_match else None
                reviews = int(reviews_match.group(1).replace(",", "")) if reviews_match else None
            except:
                rating, reviews = None, None

            restaurant_data.append((name, url, rating, reviews, city))

        except Exception as e:
            print(f"Skipped a container due to error: {e}")

    return restaurant_data


# === MAIN FLOW ===

def scrapeRestaurantNamesAndURL():
    query = "מסעדות בבאר שבע"
    city = extract_city_from_query(query)

    # Initialize DB
    conn, cursor = init_db()

    # Start browser
    driver = start_driver()
    try:
        # Run search
        search_google_maps(driver, query)
        scroll_to_end(driver)

        # Scrape data
        restaurants = extract_restaurants(driver, city)
        print(f"Found {len(restaurants)} restaurants in {city}")

        # Save to DB
        for r in restaurants:
            insert_restaurant(cursor, *r)

        conn.commit()
        print(f"Inserted {len(restaurants)} new restaurants.")
    finally:
        driver.quit()
        conn.close()



