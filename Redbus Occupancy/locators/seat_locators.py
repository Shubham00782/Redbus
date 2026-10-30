class SeatLocators:
    SELECT_SEATS_TEXT = "Select seats"
    SEATS_CONTAINER = '[class*="seatsContainer"]'
    DECK_SEAT_BUTTON = 'span[role="button"]'
    SOLD_SEATS = '[role="button"][aria-label*="availability sold"]'
    AVAILABLE_SEATS = '[role="button"][aria-label*="availability available"]'
    CLOSE_BUTTON = 'button[aria-label="Close"]'
