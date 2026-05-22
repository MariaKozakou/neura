from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from django.utils import timezone

from dispatch.models import DispatchResult, TimeSeriesPoint
from dispatch.services.battery_dispatch import STEP_HOURS


@dataclass(frozen=True)
class WeeklyReport:
    cost_with_battery_eur: float
    cost_without_battery_eur: float
    savings_eur: float
    charged_kwh: float
    discharged_kwh: float
    solar_self_consumption_pct: float
    total_solar_kwh: float
    curtailed_solar_kwh: float
    soc_chart_base64: str


def build_weekly_report() -> WeeklyReport:
    dispatch_results = list(DispatchResult.objects.order_by("timestamp"))
    input_points = list(TimeSeriesPoint.objects.order_by("timestamp"))

    cost_with_battery = sum(result.cost_with_battery_eur for result in dispatch_results)
    cost_without_battery = sum(result.cost_without_battery_eur for result in dispatch_results)
    charged_kwh = sum(result.charge_kw * STEP_HOURS for result in dispatch_results)
    discharged_kwh = sum(result.discharge_kw * STEP_HOURS for result in dispatch_results)
    curtailed_solar_kwh = sum(result.curtailed_solar_kw * STEP_HOURS for result in dispatch_results)
    total_solar_kwh = sum(point.solar_kw * STEP_HOURS for point in input_points)

    if total_solar_kwh:
        self_consumption_pct = 100 * (total_solar_kwh - curtailed_solar_kwh) / total_solar_kwh
    else:
        self_consumption_pct = 0.0

    return WeeklyReport(
        cost_with_battery_eur=round(cost_with_battery, 2),
        cost_without_battery_eur=round(cost_without_battery, 2),
        savings_eur=round(cost_without_battery - cost_with_battery, 2),
        charged_kwh=round(charged_kwh, 1),
        discharged_kwh=round(discharged_kwh, 1),
        solar_self_consumption_pct=round(self_consumption_pct, 1),
        total_solar_kwh=round(total_solar_kwh, 1),
        curtailed_solar_kwh=round(curtailed_solar_kwh, 1),
        soc_chart_base64=_build_soc_chart(dispatch_results),
    )


def _build_soc_chart(dispatch_results: list[DispatchResult]) -> str:
    timestamps = [timezone.localtime(result.timestamp) for result in dispatch_results]
    soc_values = [result.soc_kwh for result in dispatch_results]

    figure, axis = plt.subplots(figsize=(10, 3.8), dpi=140)
    axis.plot(timestamps, soc_values, color="#0f766e", linewidth=2)
    axis.fill_between(timestamps, soc_values, color="#99f6e4", alpha=0.35)
    axis.set_title("Battery state of charge over the representative week")
    axis.set_ylabel("SoC (kWh)")
    axis.set_xlabel("Time")
    axis.set_ylim(0, 400)
    axis.grid(True, alpha=0.25)
    figure.autofmt_xdate()
    figure.tight_layout()

    buffer = BytesIO()
    figure.savefig(buffer, format="png")
    plt.close(figure)
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode("ascii")
