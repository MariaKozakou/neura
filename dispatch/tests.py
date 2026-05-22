from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from dispatch.models import DispatchResult, TimeSeriesPoint
from dispatch.services.battery_dispatch import (
    MAX_POWER_KW,
    MAX_SOC_KWH,
    MIN_SOC_KWH,
    simulate_dispatch,
)


class DispatchPolicyTests(TestCase):
    def test_soc_stays_inside_battery_limits(self):
        steps = simulate_dispatch(_sample_day_points())

        self.assertGreaterEqual(min(step.soc_kwh for step in steps), MIN_SOC_KWH)
        self.assertLessEqual(max(step.soc_kwh for step in steps), MAX_SOC_KWH)

    def test_charge_and_discharge_power_stay_under_cap(self):
        steps = simulate_dispatch(_sample_day_points())

        self.assertLessEqual(max(step.charge_kw for step in steps), MAX_POWER_KW)
        self.assertLessEqual(max(step.discharge_kw for step in steps), MAX_POWER_KW)

    def test_discharge_never_creates_grid_export(self):
        point = _point(hour=12, solar_kw=20, load_kw=80, price=0.30)

        step = simulate_dispatch([point])[0]

        self.assertEqual(step.action, DispatchResult.ACTION_DISCHARGE)
        self.assertLessEqual(step.discharge_kw, point.load_kw - point.solar_kw)
        self.assertGreaterEqual(step.grid_import_kw, 0)

    def test_surplus_solar_is_curtailed_when_battery_is_full(self):
        points = [_point(hour=12, solar_kw=200, load_kw=10, price=0.30) for _ in range(20)]

        steps = simulate_dispatch(points)

        self.assertEqual(steps[-1].soc_kwh, MAX_SOC_KWH)
        self.assertGreater(steps[-1].curtailed_solar_kw, 0)


def _sample_day_points() -> list[TimeSeriesPoint]:
    return [
        _point(hour=hour, solar_kw=solar_kw, load_kw=load_kw, price=price)
        for hour, solar_kw, load_kw, price in [
            (0, 0, 80, 0.15),
            (6, 20, 90, 0.15),
            (9, 150, 100, 0.30),
            (12, 200, 120, 0.30),
            (15, 80, 180, 0.30),
            (18, 10, 160, 0.30),
            (23, 0, 90, 0.15),
        ]
    ]


def _point(hour: int, solar_kw: float, load_kw: float, price: float) -> TimeSeriesPoint:
    timestamp = timezone.make_aware(datetime(2019, 7, 1) + timedelta(hours=hour))
    return TimeSeriesPoint(
        timestamp=timestamp,
        solar_kw=solar_kw,
        load_kw=load_kw,
        grid_price_eur_per_kwh=price,
    )
