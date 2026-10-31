"""Konstanten für die urbanhive-homefarm-Integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "urbanhive"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_HOST = "host"
CONF_PREFER_CLOUD = "prefer_cloud"
CONF_FARM_ID = "farm_id"

# Firebase-Client-Konfiguration aus der öffentlichen urbanhive-App (de.urbanhive.app).
# Ein Firebase-API-Key ist ein Client-Identifikator, kein Geheimnis: Er steckt in jeder
# App-Installation und wird von Firebase über serverseitige Regeln abgesichert, nicht über
# seine Vertraulichkeit. Deshalb kann er hier stehen; die eigentliche Anmeldung braucht
# weiterhin E-Mail und Passwort des Nutzers.
FIREBASE_API_KEY = "AIzaSyBi0hzKeGedsxSuiXtH4J2cRMfCyAaoGn0"
FIREBASE_SIGNIN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

# Cloud-Backend (nur als Rückfalloption und für den Pflanzenkatalog).
CLOUD_BASE = "https://urbanhive-prod-xnlyfhorpq-ez.a.run.app/v2"

# Die App hängt diese Parameter an jede Backend-Anfrage; ohne sie antworten manche
# Endpunkte (z. B. der Pflanzenkatalog) mit HTTP 400.
APP_VERSION = "5.1.1 (288)"
CHANNEL = "urbanhive"
DEFAULT_LANG = "de"

# Die Farm nimmt lokal nur Anfragen an, deren Authorization-Token an einer festen Stelle
# ein zusätzliches Zeichen trägt — so macht es die App in ihrem lokalen HTTP-Client. Das
# Cloud-Backend will dagegen das unveränderte Token.
LOCAL_TOKEN_MARKER_INDEX = 436
LOCAL_TOKEN_MARKER = "G"

LOCAL_PORT = 80
# Die Farm (ESP32) nimmt TCP-Verbindungen teils erst nach gut einer Sekunde an.
LOCAL_TIMEOUT = 8
CLOUD_TIMEOUT = 20

DEFAULT_SCAN_INTERVAL = timedelta(seconds=120)
CATALOG_REFRESH = timedelta(hours=24)
TASK_REFRESH = timedelta(minutes=15)

# Beleuchtungsmodus: „Mach's individuell“ bzw. „Grow-Modus“ in der App.
LIGHT_MODES = ["custom", "grow"]

# Neue Dimmzeit wie in der App: 50 %, ohne Wochentag (= jeden Tag). Mit einem
# Wochentag-Wert wie „ALL“ lehnt die Farm die Einstellung ab (HTTP 400).
DEFAULT_DIM = {
    "brightness": 50,
    "startHour": 12,
    "startMinute": 0,
    "endHour": 14,
    "endMinute": 0,
    "weekDay": None,
}

# Aufgabentypen der App (für lesbare Aufgabentexte).
TASK_TYPES = (
    "CLEANING",
    "FERTILIZER",
    "HARVEST_MIN",
    "HARVEST_MAX",
    "TEMPERATURE",
    "UPDATE_FARM",
    "WATERLEVEL_LOW",
)

MANUFACTURER = "urbanhive"
MODEL = "homefarm"

# Wasserstand: Die Farm liefert je Ebene 0 (leer) oder 100 (voll).
WATER_EMPTY = 0
