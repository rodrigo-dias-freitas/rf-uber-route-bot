import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DAILY_META_BRL = float(os.getenv("DAILY_META_BRL", "550.00"))
CUTOFF_HOUR = os.getenv("CUTOFF_HOUR", "00:00")

ALLOWED_ZONES = [
    "Zona Norte / Jacarepaguá",
    "Zona Sul",
    "Tijuca",
    "Centro",
]