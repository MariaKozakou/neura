from django.core.management.base import BaseCommand

from dispatch.models import DispatchResult, TimeSeriesPoint
from dispatch.services.battery_dispatch import persist_dispatch_results
from dispatch.services.data_generation import build_week_points


class Command(BaseCommand):
    help = "Seed one representative 15-minute week of solar, hotel load, and TOU prices."

    def handle(self, *args, **options):
        TimeSeriesPoint.objects.all().delete()
        DispatchResult.objects.all().delete()

        # Store generated inputs in the database so report views do not hide
        # data assumptions inside presentation code.
        points = [
            TimeSeriesPoint(
                timestamp=point.timestamp,
                solar_kw=point.solar_kw,
                load_kw=point.load_kw,
                grid_price_eur_per_kwh=point.grid_price_eur_per_kwh,
            )
            for point in build_week_points()
        ]

        TimeSeriesPoint.objects.bulk_create(points)
        dispatch_count = persist_dispatch_results()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(points)} input points and {dispatch_count} dispatch results."
            )
        )
