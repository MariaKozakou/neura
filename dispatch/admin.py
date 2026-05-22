from django.contrib import admin

from .models import DispatchResult, TimeSeriesPoint


@admin.register(TimeSeriesPoint)
class TimeSeriesPointAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "solar_kw", "load_kw", "grid_price_eur_per_kwh")
    ordering = ("timestamp",)


@admin.register(DispatchResult)
class DispatchResultAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "action",
        "soc_kwh",
        "grid_import_kw",
        "curtailed_solar_kw",
    )
    ordering = ("timestamp",)
