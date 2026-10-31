"""Constants for the urbanhive homefarm integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "urbanhive"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_PREFER_CLOUD = "prefer_cloud"
CONF_FARM_ID = "farm_id"

# Firebase client configuration of the public urbanhive app (de.urbanhive.app).
# A Firebase API key identifies the client app; it is not a secret. It ships with every
# install of the app and Firebase protects the project with server-side rules, not by
# keeping the key private. Signing in still requires the user's own credentials.
FIREBASE_API_KEY = "AIzaSyBi0hzKeGedsxSuiXtH4J2cRMfCyAaoGn0"
FIREBASE_SIGNIN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

# urbanhive cloud backend: sign-in, plant catalog, plant slots, tasks and flags.
CLOUD_BASE = "https://urbanhive-prod-xnlyfhorpq-ez.a.run.app/v2"

# The app adds these parameters to every backend request; some endpoints (for example
# the plant catalog) answer HTTP 400 without them.
APP_VERSION = "5.1.1 (288)"
CHANNEL = "urbanhive"
DEFAULT_LANG = "de"

# Locally the farm only accepts an Authorization token that carries one extra character
# at a fixed position - that is what the app's local HTTP client sends. The cloud
# backend expects the unmodified token.
LOCAL_TOKEN_MARKER_INDEX = 436
LOCAL_TOKEN_MARKER = "G"

LOCAL_PORT = 80
# The farm (ESP32) sometimes takes more than a second to accept a TCP connection.
LOCAL_TIMEOUT = 8
CLOUD_TIMEOUT = 20

DEFAULT_SCAN_INTERVAL = timedelta(seconds=120)
CATALOG_REFRESH = timedelta(hours=24)
TASK_REFRESH = timedelta(minutes=15)

MANUFACTURER = "urbanhive"
MODEL = "homefarm"

# Water level per level: the farm reports 0 (empty) or 100 (full).
WATER_EMPTY = 0

# Light mode: "custom" and "grow mode" in the app.
LIGHT_MODES = ["custom", "grow"]

# New dimming window like the app creates it: 50 %, no weekday (= every day). With a
# weekday value such as "ALL" the farm rejects the update (HTTP 400).
DEFAULT_DIM = {
    "brightness": 50,
    "startHour": 12,
    "startMinute": 0,
    "endHour": 14,
    "endMinute": 0,
    "weekDay": None,
}

# Flag holding the date of the last cleaning; the app treats a cleaning as valid for
# 28 days.
FLAG_CLEANING = "farm.cleaning-date"
CLEANING_INTERVAL = timedelta(days=28)
