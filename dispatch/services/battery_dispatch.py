from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Iterable

from dispatch.models import DispatchResult, TimeSeriesPoint


BATTERY_CAPACITY_KWH = 400.0
MAX_POWER_KW = 200.0

# The PDF gives SoC limits as percentages. The simulation works in kWh, so
# 10% of 400 kWh becomes 40 kWh and 95% becomes 380 kWh.
MIN_SOC_KWH = BATTERY_CAPACITY_KWH * 0.10
MAX_SOC_KWH = BATTERY_CAPACITY_KWH * 0.95

# Round-trip efficiency means charge -> store -> discharge. Splitting it into
# equal one-way efficiencies lets us apply losses when charging and discharging.
ROUND_TRIP_EFFICIENCY = 0.88
ONE_WAY_EFFICIENCY = sqrt(ROUND_TRIP_EFFICIENCY)

# Each input row is a 15-minute interval, which is 0.25 hours.
STEP_HOURS = 0.25
DAY_RATE_EUR_PER_KWH = 0.30


@dataclass(frozen=True)
class DispatchStep:
    timestamp: datetime
    action: str
    charge_kw: float
    discharge_kw: float
    soc_kwh: float
    grid_import_kw: float
    curtailed_solar_kw: float
    cost_with_battery_eur: float
    cost_without_battery_eur: float


def simulate_dispatch(points: Iterable[TimeSeriesPoint]) -> list[DispatchStep]:
    """Run a greedy solar-first battery dispatch over 15-minute input points."""

    # Start the week half full. This variable is the battery "memory": after
    # each 15-minute step, the updated value is reused by the next step.
    soc_kwh = BATTERY_CAPACITY_KWH * 0.50
    results: list[DispatchStep] = []

    for point in points:
        # Rule 1: cover hotel load from solar first.
        solar_to_load_kw = min(point.solar_kw, point.load_kw)
        remaining_load_kw = point.load_kw - solar_to_load_kw
        surplus_solar_kw = point.solar_kw - solar_to_load_kw

        charge_kw = 0.0
        discharge_kw = 0.0
        curtailed_solar_kw = 0.0

        if surplus_solar_kw > 0:
            # Rule 2: if solar is left over, try to store it in the battery.
            # The helper returns the new SoC, which carries into the next loop.
            charge_kw, soc_kwh, curtailed_solar_kw = _charge_from_surplus(
                surplus_solar_kw=surplus_solar_kw,
                soc_kwh=soc_kwh,
            )
        elif remaining_load_kw > 0 and point.grid_price_eur_per_kwh >= DAY_RATE_EUR_PER_KWH:
            # Rule 3: during expensive hours, discharge only enough to cover
            # remaining hotel load. This prevents grid export.
            discharge_kw, soc_kwh = _discharge_to_cover_load(
                remaining_load_kw=remaining_load_kw,
                soc_kwh=soc_kwh,
            )

        # Anything still not covered by solar or battery must come from the grid.
        grid_import_kw = max(0.0, remaining_load_kw - discharge_kw)
        no_battery_grid_import_kw = max(0.0, point.load_kw - point.solar_kw)

        if charge_kw > 0:
            action = DispatchResult.ACTION_CHARGE
        elif discharge_kw > 0:
            action = DispatchResult.ACTION_DISCHARGE
        else:
            action = DispatchResult.ACTION_IDLE

        results.append(
            DispatchStep(
                timestamp=point.timestamp,
                action=action,
                charge_kw=round(charge_kw, 6),
                discharge_kw=round(discharge_kw, 6),
                soc_kwh=round(soc_kwh, 6),
                grid_import_kw=round(grid_import_kw, 6),
                curtailed_solar_kw=round(curtailed_solar_kw, 6),
                cost_with_battery_eur=round(
                    grid_import_kw * STEP_HOURS * point.grid_price_eur_per_kwh,
                    6,
                ),
                cost_without_battery_eur=round(
                    no_battery_grid_import_kw * STEP_HOURS * point.grid_price_eur_per_kwh,
                    6,
                ),
            )
        )

    return results


def persist_dispatch_results() -> int:
    """Run dispatch for all input points and store the outputs in SQLite."""

    points = TimeSeriesPoint.objects.order_by("timestamp")
    steps = simulate_dispatch(points)

    DispatchResult.objects.all().delete()
    DispatchResult.objects.bulk_create(
        [
            DispatchResult(
                timestamp=step.timestamp,
                action=step.action,
                charge_kw=step.charge_kw,
                discharge_kw=step.discharge_kw,
                soc_kwh=step.soc_kwh,
                grid_import_kw=step.grid_import_kw,
                curtailed_solar_kw=step.curtailed_solar_kw,
                cost_with_battery_eur=step.cost_with_battery_eur,
                cost_without_battery_eur=step.cost_without_battery_eur,
            )
            for step in steps
        ]
    )

    return len(steps)


def _charge_from_surplus(surplus_solar_kw: float, soc_kwh: float) -> tuple[float, float, float]:
    # Headroom is how much empty space remains before the 95% SoC ceiling.
    headroom_kwh = MAX_SOC_KWH - soc_kwh

    # Convert that energy headroom into a max charging power for this 15-minute
    # step, including charging losses.
    max_charge_from_headroom_kw = headroom_kwh / (STEP_HOURS * ONE_WAY_EFFICIENCY)

    # The actual charge power is limited by solar surplus, inverter power, and
    # remaining battery space.
    charge_kw = min(surplus_solar_kw, MAX_POWER_KW, max_charge_from_headroom_kw)

    # Charging increases SoC, but only after one-way efficiency losses.
    new_soc_kwh = min(MAX_SOC_KWH, soc_kwh + charge_kw * STEP_HOURS * ONE_WAY_EFFICIENCY)
    curtailed_solar_kw = max(0.0, surplus_solar_kw - charge_kw)

    return charge_kw, new_soc_kwh, curtailed_solar_kw


def _discharge_to_cover_load(remaining_load_kw: float, soc_kwh: float) -> tuple[float, float]:
    # Available energy is only what sits above the 10% SoC floor.
    available_kwh = soc_kwh - MIN_SOC_KWH

    # Convert available stored energy into max deliverable power for this step,
    # accounting for discharge losses.
    max_discharge_from_soc_kw = available_kwh * ONE_WAY_EFFICIENCY / STEP_HOURS

    # The actual discharge is capped by hotel need, inverter power, and SoC.
    discharge_kw = min(remaining_load_kw, MAX_POWER_KW, max_discharge_from_soc_kw)

    # Discharging reduces SoC. More energy leaves the battery than reaches load
    # because of one-way efficiency losses.
    new_soc_kwh = max(MIN_SOC_KWH, soc_kwh - discharge_kw * STEP_HOURS / ONE_WAY_EFFICIENCY)

    return discharge_kw, new_soc_kwh
