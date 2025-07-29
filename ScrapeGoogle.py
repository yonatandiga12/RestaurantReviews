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
    #options.add_argument("--headless")  # This hides the browser window
    options.add_argument("--disable-gpu")  # (optional but recommended for headless mode)
    options.add_argument("--window-size=1920,1080")  # Set a standard window size
    options.add_argument("--no-sandbox")  # Useful for some Linux systems
    options.add_argument("--disable-dev-shm-usage")  # Avoid shared memory issues
    #options.add_argument("--start-maximized")
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


# def add_star_rating_columns(cursor):
#     # Add columns if they don't already exist
#     columns = ['rating_1_count', 'rating_2_count', 'rating_3_count', 'rating_4_count', 'rating_5_count']
#     for col in columns:
#         try:
#             cursor.execute(f"ALTER TABLE restaurants ADD COLUMN {col} INTEGER DEFAULT -1")
#         except sqlite3.OperationalError:
#             # Column already exists
#             pass

def scrape_and_update_rating_distribution(driver, conn, cursor, limit=10):
    cursor.execute("SELECT id, url FROM restaurants WHERE rating_1_count IS NULL LIMIT ?", (limit,))
    rows = cursor.fetchall()

    for restaurant_id, url in rows:
        print(f"Scraping rating distribution for restaurant ID {restaurant_id}")
        try:
            driver.get(url)
            time.sleep(3)

            # NEW: Click the 'ביקורות' tab
            try:
                review_tab = driver.find_element(By.XPATH, '//button[.//div[contains(text(),"ביקורות")]]')
                review_tab.click()
                time.sleep(2)
            except Exception as e:
                print("Could not click ביקורות tab:", e)

            # Continue with star breakdown scraping
            elements = driver.find_elements(By.XPATH, '//tr[@class="BHOKXe"]')
            star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

            for el in elements:
                try:
                    label = el.get_attribute("aria-label")
                    label = re.sub(r"[\u200e\u200f\u202b]", "", label)

                    match = re.search(r"(\d)[^\d]+כוכבים[^\d]+([\d,]+)", label)
                    if match:
                        stars = int(match.group(1))
                        count = int(match.group(2).replace(",", ""))
                        star_counts[stars] = count
                    else:
                        print("No match for label:", label)
                except Exception as e:
                    print(f"Error parsing row: {e}")

            # Update DB
            cursor.execute("""
                    UPDATE restaurants
                    SET rating_1_count = ?, rating_2_count = ?, rating_3_count = ?, rating_4_count = ?, rating_5_count = ?
                    WHERE id = ?
                """, (
                star_counts[1], star_counts[2], star_counts[3],
                star_counts[4], star_counts[5], restaurant_id
            ))
            conn.commit()

        except Exception as e:
            print(f"Failed to scrape {url}: {e}")















# === MAIN FLOW ===

def scrapeRestaurantNamesAndURL():
    query = "מסעדות בתל אביב"
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



def scrapeRestaurantsRatings():
    conn, cursor = init_db()
    #add_star_rating_columns(cursor)
    conn.commit()

    driver = start_driver()
    try:
        scrape_and_update_rating_distribution(driver, conn, cursor, limit=60)
    finally:
        driver.quit()
        conn.close()

