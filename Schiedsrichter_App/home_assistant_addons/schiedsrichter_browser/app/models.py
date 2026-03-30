from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import re
from typing import Any


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def strip_team_suffix(team_name: str) -> str:
    if not team_name:
        return ""
    return re.sub(r"\s*\[[^\]]+\]\s*$", "", str(team_name)).strip()


def clean_hall_name(hall_name: str) -> str:
    hall_name = str(hall_name or "").strip()
    return re.sub(r"^\d+\s+", "", hall_name)


def extract_league(team_name: str, fallback: str = "") -> str:
    match = re.search(r"\[([^\]]+)\]", str(team_name or ""))
    if match:
        return match.group(1).strip()
    return str(fallback or "").strip()


def _format_date(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()

    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return text


def _format_time(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()

    if isinstance(value, datetime):
        return value.strftime("%H:%M")

    if hasattr(value, "strftime"):
        try:
            return value.strftime("%H:%M")
        except Exception:
            pass

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M")
        except ValueError:
            continue

    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"

    return text


def parse_match_datetime(date_text: str, time_text: str) -> datetime | None:
    if not date_text:
        return None

    combined = f"{date_text} {time_text or '00:00'}".strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(combined, fmt)
        except ValueError:
            continue
    return None


def calculate_time_window(
    date_text: str,
    time_text: str,
    minutes_before: int,
    minutes_after: int,
) -> tuple[str, str]:
    match_dt = parse_match_datetime(date_text, time_text)
    if match_dt is None:
        return "", ""

    departure = match_dt - timedelta(minutes=minutes_before)
    return_trip = match_dt + timedelta(minutes=minutes_after)
    return departure.strftime("%H:%M"), return_trip.strftime("%H:%M")


@dataclass(slots=True)
class Appointment:
    match_id: str
    date: str
    time: str
    league: str
    home_team: str
    away_team: str
    hall_id: str
    hall_name: str
    hall_address: str = ""
    referees: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Appointment":
        raw_home = str(row.get("Heimmannschaft") or "")
        raw_away = str(row.get("Gastmannschaft") or "")
        hall_id = str(row.get("H.Nr") or row.get("Halle") or "").strip()
        referee_text = str(row.get("Namen") or "").strip()
        referees = [
            entry.strip()
            for entry in referee_text.split("/")
            if entry.strip() and entry.strip() != "-"
        ]
        return cls(
            match_id=str(row.get("Sp.Nr") or "").strip(),
            date=_format_date(row.get("Datum")),
            time=_format_time(row.get("Zeit")),
            league=str(row.get("Staffel") or row.get("Spielklasse") or extract_league(raw_home)).strip(),
            home_team=strip_team_suffix(raw_home),
            away_team=strip_team_suffix(raw_away),
            hall_id=hall_id,
            hall_name=clean_hall_name(row.get("Hallename") or row.get("Hallenname_cleaned") or ""),
            hall_address=str(row.get("Halle Kontakt") or "").strip(),
            referees=referees,
        )

    @property
    def hall_code(self) -> str:
        digits = re.findall(r"\d+", self.hall_id)
        if not digits:
            return ""
        return digits[-1][-3:]

    @property
    def display_name(self) -> str:
        return f"{self.date} | {self.league}: {self.home_team} vs {self.away_team}"


@dataclass(slots=True)
class Profile:
    first_name: str
    last_name: str
    city_zip: str
    street: str
    start_location: str
    minutes_before: int = 75
    minutes_after: int = 120
    match_fee: float = 25.0
    km_rate: float = 0.38

    @property
    def profile_name(self) -> str:
        return f"{self.first_name.strip()} {self.last_name.strip()}".strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        return cls(
            first_name=str(data.get("first_name") or "").strip(),
            last_name=str(data.get("last_name") or "").strip(),
            city_zip=str(data.get("city_zip") or "").strip(),
            street=str(data.get("street") or "").strip(),
            start_location=str(data.get("start_location") or "").strip(),
            minutes_before=int(float(data.get("minutes_before", 75) or 75)),
            minutes_after=int(float(data.get("minutes_after", 120) or 120)),
            match_fee=float(data.get("match_fee", 25.0) or 25.0),
            km_rate=float(data.get("km_rate", 0.38) or 0.38),
        )
