class ResultsLocators:
    BUSES_FOUND = 'div[class*="busesFoundText"]'
    BUS_CARD = "ul[aria-label='Bus search results'] > li:has(button[class*='viewSeatsBtn'])"
    NUMBER_PLATE = "[class*='numberPlate']"
    TRAVELS_NAME = "[class*='travelsName']"
    BUS_TYPE = "[class*='busType']"
    RATING = "[class*='rating___']"
    RATING_CHIP = "[aria-label*='stars']"
    BOARDING_TIME = "[class*='boardingTime']"
    DROPPING_TIME = "[class*='droppingTime']"
    VIEW_SEATS = "button[class*='viewSeatsBtn']"
