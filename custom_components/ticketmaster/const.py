"""Constants for the Ticketmaster integration."""

from homeassistant.const import CONF_API_KEY

DOMAIN = "ticketmaster"
NAME = "Gig Finder"

CONF_RADIUS_MILES = "radius_miles"
CONF_GENRE = "genre"
CONF_GENRE_ID = "genre_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_FATSOMA_PAGE_IDS = "fatsoma_page_ids"
CONF_FATSOMA_SEARCH = "fatsoma_page_search"
CONF_SKIDDLE_API_KEY = "skiddle_api_key"
CONF_SKIDDLE_VENUE_IDS = "skiddle_venue_ids"
CONF_SKIDDLE_GENRES = "skiddle_genre_ids"
CONF_SKIDDLE_SEARCH = "skiddle_venue_search"

DEFAULT_RADIUS_MILES = 50
DEFAULT_GENRE = ""
DEFAULT_SCAN_INTERVAL_MINUTES = 360
MIN_SCAN_INTERVAL_MINUTES = 30
DEFAULT_FATSOMA_PAGE_IDS: list[str] = []
DEFAULT_SKIDDLE_VENUE_IDS: list[str] = []
DEFAULT_SKIDDLE_GENRES: list[str] = []

API_BASE_URL = "https://app.ticketmaster.com/discovery/v2"

FATSOMA_BASE_URL = "https://api.fatsoma.com/v1"
FATSOMA_GIGS_CATEGORY_ID = "1b24e0f9-325f-4ecc-a95c-d3a9ba767da8"

SKIDDLE_API_BASE_URL = "https://www.skiddle.com/api/v1"

UNITS = "mi"