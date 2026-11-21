from dataclasses import dataclass
from datetime import datetime
import re
from app.config import ALLOWED_ZONES, DAILY_META_BRL

ZONE_ALIASES = {
    "zn": "Zona Norte / Jacarepaguá",
    "zona norte": "Zona Norte / Jacarepaguá",
    "jacarepagua": "Zona Norte / Jacarepaguá",
    "jacarepaguá": "Zona Norte / Jacarepaguá",
    "jpa": "Zona Norte / Jacarepaguá",
    "zs": "Zona Sul",
    "zona sul": "Zona Sul",
    "copacabana": "Zona Sul",
    "ippanema": "Zona Sul",
    "ipanema": "Zona Sul",
    "leblon": "Zona Sul",
    "botafogo": "Zona Sul",
    "gavea": "Zona Sul",
    "gávea": "Zona Sul",
    "rio sul": "Zona Sul",
    "tijuca": "Tijuca",
    "grande tijuca": "Tijuca",
    "centro": "Centro",
    "rodoviaria": "Centro",
    "rodoviária": "Centro",
}


@dataclass
class DayState:
    date_str: str
    meta_brl: float = DAILY_META_BRL
    chart_image_bytes: bytes | None = None
    chart_mime_type: str = "image/jpeg"
    current_amount_brl: float = 0.0
    current_zone: str = "Zona Sul"
    last_updated_str: str = ""


def normalize_zone(raw_text: str) -> str:
    cleaned = raw_text.strip().lower()
    if cleaned in ZONE_ALIASES:
        return ZONE_ALIASES[cleaned]
    for zone in ALLOWED_ZONES:
        if zone.lower() in cleaned:
            return zone
    for alias, canonical in ZONE_ALIASES.items():
        if alias in cleaned:
            return canonical
    return raw_text.strip().title()


def parse_status_message(text: str) -> tuple[float | None, str | None, str | None]:
    """
    Aceita formatos rápidos como:
    - "170,46 rio sul"
    - "377.84 copacabana 20:59"
    """
    text = text.strip()
    match = re.match(
        r"^\s*R?\$?\s*(\d+(?:[.,]\d{1,2})?)\s+([a-zA-ZÀ-ÿ\s/]+?)(?:\s+(\d{1,2}[:h]\d{2}))?\s*$",
        text,
    )
    if not match:
        return None, None, None

    amount = float(match.group(1).replace(",", "."))
    zone = normalize_zone(match.group(2))
    time_str = None
    if match.group(3):
        time_str = match.group(3).replace("h", ":")
        parts = time_str.split(":")
        time_str = f"{int(parts[0]):02d}:{int(parts[1]):02d}"

    return amount, zone, time_str


def calc_remaining_and_rate(
    current_amount: float,
    now_dt: datetime,
    meta_brl: float = DAILY_META_BRL,
) -> tuple[float, float, float]:
    remaining = max(0.0, meta_brl - current_amount)
    end_of_day = now_dt.replace(hour=23, minute=59, second=59, microsecond=0)
    hours_left = max(0.25, (end_of_day - now_dt).total_seconds() / 3600.0)
    needed_per_hour = remaining / hours_left
    return remaining, hours_left, needed_per_hour