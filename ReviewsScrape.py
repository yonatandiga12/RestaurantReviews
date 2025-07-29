import re
import sqlite3
import time
import uuid

from selenium.webdriver.common.by import By

from ScrapeGoogle import DB_PATH, start_driver


def init_reviews_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER,
            stars INTEGER,
            text TEXT,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
        );
    """)



def insert_reviews(cursor, reviews):
    cursor.executemany("""
        INSERT OR IGNORE INTO reviews (review_id, restaurant_id, stars, text)
        VALUES (?, ?, ?, ?)
    """, [
        (r["review_id"], r["restaurant_id"], r["stars"], r["text"])
        for r in reviews
    ])





def scrape_and_store_reviews(driver, cursor, url, restaurant_id, max_scrolls=2):

    print(f"🔍 Scraping reviews for restaurant ID {restaurant_id}")
    driver.get(url)
    time.sleep(4)

    # Step 1: Click the 'ביקורות' tab
    try:
        review_tab = driver.find_element(By.XPATH, '//button[.//div[contains(text(),"ביקורות")]]')
        review_tab.click()
        time.sleep(2)
    except Exception as e:
        print("❌ Could not click 'ביקורות' tab:", e)
        return

    # Step 2: Scroll reviews panel
    try:
        scrollable_div = driver.find_element(By.XPATH, '//div[@class="m6QErb DxyBCb kA9KIf dS8AEf XiKgde "]')
        for _ in range(max_scrolls):
            driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
            time.sleep(1.5)
    except Exception as e:
        print("❌ Could not scroll reviews:", e)

    # Step 3: Expand all 'עוד' buttons
    more_buttons = driver.find_elements(By.CLASS_NAME, "w8nwRe")
    for btn in more_buttons:
        try:
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.2)
        except Exception as e:
            print("⚠️ Failed to click 'עוד':", e)

    # Step 4: Find review containers
    review_containers = driver.find_elements(By.XPATH, '//div[contains(@class, "jftiEf")]')
    print(f"📦 Found {len(review_containers)} review containers")

    reviews = []

    for container in review_containers:
        try:
            # Review text
            try:
                text_element = container.find_element(By.CLASS_NAME, "wiI7pd")
                text = text_element.text.strip()
            except:
                text = ""

            # Review stars
            try:
                star_element = container.find_element(By.CLASS_NAME, "kvMYJc")
                star_label = star_element.get_attribute("aria-label")
                star_label = re.sub(r"[\u200e\u200f\u202b]", "", star_label)

                match = re.search(r"(\d+)\s+כוכבים", star_label)
                if match:
                    stars = int(match.group(1))
                elif "כוכב אחד" in star_label:
                    stars = 1
                else:
                    stars = None
            except:
                stars = None

            if text and stars is not None:
                reviews.append((restaurant_id, stars, text))

        except Exception as e:
            print("⚠️ Error processing container:", e)

    # Step 5: Insert reviews into DB
    if reviews:
        cursor.executemany("""
            INSERT INTO reviews (restaurant_id, stars, text)
            VALUES (?, ?, ?)
        """, reviews)
        print(f"✅ Inserted {len(reviews)} reviews into DB")
    else:
        print("⚠️ No reviews to insert.")




def scrape_all_reviews_for_pending_restaurants(db_path=DB_PATH, limit=1):
    # Setup DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Make sure reviews table exists
    init_reviews_table(cursor)
    conn.commit()

    # Start headless Chrome
    driver = start_driver()

    try:
        # Find restaurants that do NOT yet have reviews
        cursor.execute("""
            SELECT id, url FROM restaurants
            WHERE id NOT IN (SELECT DISTINCT restaurant_id FROM reviews)
            LIMIT ?
        """, (limit,))
        restaurants = cursor.fetchall()

        print(f"Scraping reviews for {len(restaurants)} restaurants...")

        for restaurant_id, url in restaurants:
            print(f"\n📌 Scraping restaurant ID {restaurant_id}")
            try:
                scrape_and_store_reviews(driver, cursor, url, restaurant_id)
                conn.commit()
            except Exception as e:
                print(f"❌ Failed to scrape restaurant {restaurant_id}: {e}")

    finally:
        driver.quit()
        conn.close()
        print("✅ Finished scraping reviews.")
