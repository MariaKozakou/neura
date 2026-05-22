from __future__ import annotations

import json
import os
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import pi, sin
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone


LIMASSOL_LAT = 34.7071
LIMASSOL_LON = 33.0226
PV_CAPACITY_KW = 200.0
WEEK_START = datetime(2019, 7, 1, 0, 0)
STEPS_PER_HOUR = 4
WEEK_STEPS = 7 * 24 * STEPS_PER_HOUR
SOLAR_FIXTURE_PATH = settings.BASE_DIR / "data" / "solar_renewables_ninja_limassol_2019_week.csv"


@dataclass(frozen=True)
class InputPoint:
    timestamp: datetime
    solar_kw: float
    load_kw: float
    grid_price_eur_per_kwh: float


def build_week_points() -> list[InputPoint]:
    solar_profile = _get_solar_profile_kw()

    return [
        InputPoint(
            timestamp=timezone.make_aware(WEEK_START + timedelta(minutes=15 * step)),
            solar_kw=round(solar_profile[step], 3),
            load_kw=round(_hotel_load_kw(step), 3),
            grid_price_eur_per_kwh=_tou_price_eur_per_kwh(step),
        )
        for step in range(WEEK_STEPS)
    ]


def _get_solar_profile_kw() -> list[float]:
    if SOLAR_FIXTURE_PATH.exists():
        return _read_solar_fixture_kw(SOLAR_FIXTURE_PATH)

    token = os.environ.get("RENEWABLES_NINJA_TOKEN")
    if token:
        solar_profile = _fetch_renewables_ninja_solar_kw(token)
        _write_solar_fixture_kw(SOLAR_FIXTURE_PATH, solar_profile)
        return solar_profile

    # Fallback keeps the command runnable without private API credentials.
    return [_synthetic_clear_sky_solar_kw(step) for step in range(WEEK_STEPS)]


def _fetch_renewables_ninja_solar_kw(token: str) -> list[float]:
    params = {
        "lat": LIMASSOL_LAT,
        "lon": LIMASSOL_LON,
        "date_from": "2019-07-01",
        "date_to": "2019-07-07",
        "dataset": "merra2",
        "capacity": PV_CAPACITY_KW,
        "system_loss": 0.1,
        "tracking": 0,
        "tilt": 35,
        "azim": 180,
        "format": "json",
    }
    url = "https://www.renewables.ninja/api/data/pv?" + urlencode(params)
    request = Request(url, headers={"Authorization": f"Token {token}"})

    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    hourly_kw = [
        float(row["electricity"])
        for _, row in sorted(payload["data"].items(), key=lambda item: item[0])
    ]
    return _resample_hourly_to_15_min(hourly_kw)


def _resample_hourly_to_15_min(hourly_kw: list[float]) -> list[float]:
    values: list[float] = []

    for index, value in enumerate(hourly_kw):
        next_value = hourly_kw[index + 1] if index + 1 < len(hourly_kw) else value
        for quarter in range(STEPS_PER_HOUR):
            fraction = quarter / STEPS_PER_HOUR
            values.append(value + (next_value - value) * fraction)

    return values[:WEEK_STEPS]


def _read_solar_fixture_kw(path: Path) -> list[float]:
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        return [float(row["solar_kw"]) for row in reader][:WEEK_STEPS]


def _write_solar_fixture_kw(path: Path, solar_profile: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["timestamp", "solar_kw"])
        writer.writeheader()
        for step, solar_kw in enumerate(solar_profile[:WEEK_STEPS]):
            timestamp = WEEK_START + timedelta(minutes=15 * step)
            writer.writerow(
                {
                    "timestamp": timestamp.isoformat(),
                    "solar_kw": round(solar_kw, 3),
                }
            )


def _synthetic_clear_sky_solar_kw(step: int) -> float:
    timestamp = WEEK_START + timedelta(minutes=15 * step)
    hour = timestamp.hour + timestamp.minute / 60
    daylight_shape = max(0.0, sin(pi * (hour - 6) / 14))
    weekday_factor = 0.95 if timestamp.weekday() < 5 else 0.9
    return PV_CAPACITY_KW * weekday_factor * daylight_shape


def _hotel_load_kw(step: int) -> float:
    timestamp = WEEK_START + timedelta(minutes=15 * step)
    hour = timestamp.hour + timestamp.minute / 60
    is_weekend = timestamp.weekday() >= 5

    base_load = 70
    occupancy_bump = 15 if is_weekend else 5
    cooling_peak = 115 * max(0.0, sin(pi * (hour - 10) / 10))
    evening_activity = 22 * max(0.0, sin(pi * (hour - 17) / 6))

    return min(200.0, base_load + occupancy_bump + cooling_peak + evening_activity)


def _tou_price_eur_per_kwh(step: int) -> float:
    timestamp = WEEK_START + timedelta(minutes=15 * step)
    hour = timestamp.hour + timestamp.minute / 60
    return 0.30 if 9 <= hour < 23 else 0.15
