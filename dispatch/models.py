from django.db import models


class TimeSeriesPoint(models.Model):
    """One 15-minute input point for the representative hotel week."""

    timestamp = models.DateTimeField(unique=True)
    solar_kw = models.FloatField()
    load_kw = models.FloatField()
    grid_price_eur_per_kwh = models.FloatField()

    class Meta:
        ordering = ["timestamp"]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M}"


class DispatchResult(models.Model):
    """Battery simulation output for the same 15-minute timeline."""

    ACTION_CHARGE = "charge"
    ACTION_DISCHARGE = "discharge"
    ACTION_IDLE = "idle"

    ACTION_CHOICES = [
        (ACTION_CHARGE, "Charge"),
        (ACTION_DISCHARGE, "Discharge"),
        (ACTION_IDLE, "Idle"),
    ]

    timestamp = models.DateTimeField(unique=True)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    charge_kw = models.FloatField(default=0)
    discharge_kw = models.FloatField(default=0)
    soc_kwh = models.FloatField()
    grid_import_kw = models.FloatField()
    curtailed_solar_kw = models.FloatField(default=0)
    cost_with_battery_eur = models.FloatField(default=0)
    cost_without_battery_eur = models.FloatField(default=0)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action}"
