"""Constants for the Pendel integration."""

from datetime import timedelta

DOMAIN = "pendel"

CONF_PERSON = "person"
CONF_HOME_ZONE = "home_zone"
CONF_OFFICE_ZONE = "office_zone"
CONF_TRACK_LOCATION = "track_location"

TOKEN_NAME = "Home Assistant"
NOT_HOME = "not_home"

UPDATE_INTERVAL = timedelta(seconds=60)
RETRY_INTERVAL = timedelta(seconds=60)
# Pendel rejects events older than this
MAX_EVENT_AGE = timedelta(days=7)
