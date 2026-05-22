from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DispatchResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(unique=True)),
                ("action", models.CharField(choices=[("charge", "Charge"), ("discharge", "Discharge"), ("idle", "Idle")], max_length=16)),
                ("charge_kw", models.FloatField(default=0)),
                ("discharge_kw", models.FloatField(default=0)),
                ("soc_kwh", models.FloatField()),
                ("grid_import_kw", models.FloatField()),
                ("curtailed_solar_kw", models.FloatField(default=0)),
                ("cost_with_battery_eur", models.FloatField(default=0)),
                ("cost_without_battery_eur", models.FloatField(default=0)),
            ],
            options={"ordering": ["timestamp"]},
        ),
        migrations.CreateModel(
            name="TimeSeriesPoint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(unique=True)),
                ("solar_kw", models.FloatField()),
                ("load_kw", models.FloatField()),
                ("grid_price_eur_per_kwh", models.FloatField()),
            ],
            options={"ordering": ["timestamp"]},
        ),
    ]
