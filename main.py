from ReviewsScrape import scrape_all_reviews_for_pending_restaurants
from ScrapeGoogle import scrapeRestaurantNamesAndURL, scrapeRestaurantsRatings

if __name__ == '__main__':

    #scrapeRestaurantNamesAndURL()

    #scrapeRestaurantsRatings()

    NUM_OF_RESTAURANTS = 10
    MAX_SCROLLS = 20
    scrape_all_reviews_for_pending_restaurants(limit=NUM_OF_RESTAURANTS, maxScrolls=MAX_SCROLLS)
