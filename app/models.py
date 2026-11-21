from dataclasses import dataclass, field
from datetime import datetime
import re
from app.config import ALLOWED_ZONES, CUTOFF_HOUR, DAILY_META_BRL

META_DEFAULT = float(DAILY_META_BRL or 550.0)
CUTOFF_DEFAULT = CUTOFF_HOUR or "00:00"

ZONE_ALIASES: dict[str, str] = {
    "zn": "Zona Norte / Jacarepaguá",
    "zona norte": "Zona Norte / Jacarepaguá",
    "jacarepagua": "Zona Norte / Jacarepaguá",
    "jacarepaguá": "Zona Norte / Jacarepaguá",
    "jpa": "Zona Norte / Jacarepaguá",
    "barra": "Zona Norte / Jacarepaguá",
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
    meta_brl: float = META_DEFAULT
    active_zones: list[str] = field(default_factory=lambda: list(ALLOWED_ZONES))
    cutoff_hour: str = CUTOFF_DEFAULT
    start_after_str: str | None = None
    day_notes: str = ""
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


def filter_allowed_zones(zones: list[str] | None) -> list[str]:
    if not zones:
        return list(ALLOWED_ZONES)
    valid: list[str] = []
    for z in zones:
        norm = normalize_zone(z)
        if norm in ALLOWED_ZONES and norm not in valid:
            valid.append(norm)
    return valid if valid else list(ALLOWED_ZONES)


def parse_status_message(text: str) -> tuple[float | None, str | None, str | None]:
    """
    Atalho rápido para mensagens diretas no formato:
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


def _parse_hhmm(hhmm: str | None) -> tuple[int, int] | None:
    if not hhmm:
        return None
    m = re.match(r"^(\d{1,2})[:h](\d{2})$", hhmm.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return h, mi
    return None


def calc_remaining_and_rate(
    current_amount: float,
    now_dt: datetime,
    meta_brl: float = META_DEFAULT,
    cutoff_hour: str = CUTOFF_DEFAULT,
    start_after_str: str | None = None,
) -> tuple[float, float, float]:
    remaining = max(0.0, meta_brl - current_amount)

    effective_start = now_dt
    start_hm = _parse_hhmm(start_after_str)
    if start_hm:
        start_dt = now_dt.replace(hour=start_hm[0], minute=start_hm[1], second=0, microsecond=0)
        if start_dt > effective_start:
            effective_start = start_dt

    end_hm = _parse_hhmm(cutoff_hour)
    if end_hm:
        if end_hm[0] == 0 and end_hm[1] == 0:
            cutoff_dt = now_dt.replace(hour=23, minute=59, second=59, microsecond=0)
        else:
            cutoff_dt = now_dt.replace(hour=end_hm[0], minute=end_hm[1], second=0, microsecond=0)
            if cutoff_dt <= effective_start:
                cutoff_dt = now_dt.replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        cutoff_dt = now_dt.replace(hour=23, minute=59, second=59, microsecond=0)

    hours_left = max(0.25, (cutoff_dt - effective_start).total_seconds() / 3600.0)
    needed_per_hour = remaining / hours_left
    return remaining, hours_left, needed_per_hour