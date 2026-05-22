# Neura Take-Home Assessment

Small Django service for a behind-the-meter battery dispatch simulation for a Limassol hotel.

## Setup

From the cloned repository root:

```bash
pip install -r requirements.txt
python run_local.py
```

If your Windows shell uses the Python launcher, replace `python` with `py`.

Open the weekly report at http://127.0.0.1:8010/reports/weekly/.

The `run_local.py` helper applies migrations, seeds the representative week, and starts the Django development server.

Run the dispatch tests with:

```bash
python manage.py test
```

## Data

The seed command creates one representative 15-minute week with 672 points.

- Solar: reads `data/solar_renewables_ninja_limassol_2019_week.csv`, generated from Renewables.ninja point PV output near Limassol (`lat=34.6852901`, `lon=33.0332657`) for a 200 kW system using MERRA-2, 10% system loss, fixed tilt 35 degrees, and south-facing azimuth 180 degrees.
- Resampling: Renewables.ninja exported hourly `electricity` values in kW for 2019. I filtered the representative summer week from 2019-07-01 00:00 through 2019-07-07 23:00 UTC and linearly interpolated between hourly values to create 15-minute points.
- Optional solar fetch: if the CSV is missing and `RENEWABLES_NINJA_TOKEN` is set, the seed command can call Renewables.ninja with the same core assumptions and save the response as a CSV fixture. This is not required for review because the processed CSV is committed.
- Solar fallback: if neither the CSV nor a token is present, the command uses a simple clear-sky shaped PV profile so the project remains runnable for local review, but the committed CSV is the primary path.

- Load: synthetic hotel demand with a constant overnight base, higher weekend occupancy, afternoon cooling peak, and smaller evening activity bump. It is capped at 200 kW to match the task scenario.
- Grid price: stylised two-rate TOU tariff, EUR0.30/kWh from 09:00 to 23:00 and EUR0.15/kWh overnight.

Renewables.ninja API docs: https://www.renewables.ninja/documentation/api

## Current limitations and assumptions

- The repository does not include a private Renewables.ninja API token. Reviewers do not need one because the processed Renewables.ninja solar fixture is committed.
- If the fixture is deleted and no token is available, the code falls back to a documented clear-sky profile. That fallback is only for reproducibility; the submitted report uses the committed Renewables.ninja fixture.
- Hotel load is synthetic by design. I modelled a constant hotel base load, stronger afternoon cooling demand, a smaller evening activity bump, and a weekend occupancy increase, then capped the weekly peak at about 200 kW.

## Dispatch policy

The dispatch is a greedy 15-minute simulation:

- The hotel load is covered from solar first.
- Any surplus solar charges the battery, subject to the 200 kW power limit and 95% max SoC.
- If solar does not cover load during the day-rate period, the battery discharges, subject to the 200 kW power limit and 10% min SoC.
- The battery does not export to the grid; discharge is capped at the remaining hotel load.
- Surplus solar that cannot fit into the battery is counted as curtailment.
- Round-trip efficiency is 88%, modelled as equal charge/discharge one-way efficiencies of `sqrt(0.88)`.

## AI usage

I used ChatGPT/Codex as a pair-programming assistant rather than as a black box. It helped me turn the PDF brief into a small Django MVP, scaffold the project structure, draft the dispatch service, and helped with the suggested tests for the key constraints: SoC bounds, power limits, no grid export, and kW-to-kWh conversion.

I manually reviewed the battery logic, kept the architecture intentionally simple, created a documented synthetic hotel load profile, and included the processed Renewables.ninja CSV so reviewers can run the project without an API token.

AI was useful for Django boilerplate and test coverage, but I had to push back when it tried to overcomplicate the design and I double-checked the unit conversions myself.

## What I would build next

- Make the Renewables.ninja data pull repeatable end-to-end, so the CSV can be refreshed from source instead of being manually downloaded.
- Add a simple what-if form for changing PV size and battery size, since that is likely the first question a hotel or financier would ask.
- Show a day-by-day dispatch table alongside the chart, so it is easier to inspect when the battery charged, discharged, or sat idle.
- Try the same dispatch against a real EAC commercial tariff, if the tariff PDF is reachable, and compare how much the savings change.
