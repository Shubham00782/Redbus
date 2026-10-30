# RedBus route occupancy

This project opens [redBus](https://www.redbus.in/) and searches both directions of the route in `config/config.ini`. Pune to Nanded is appended to the **Occupancy Report** tab. Nanded to Pune is appended to the **Nanded to Pune** tab in the same spreadsheet. Each row has the vehicle, operator, timings, total seats, booked seats, occupancy percentage, and vacant-seat prices.

A GitHub Action runs that collection every day at 17:15 IST and can also be started by hand.

## What you need locally

- Python 3.12
- The Google service-account JSON key. Do not commit it. `.gitignore` already excludes `config/*.json`.
- The spreadsheet shared with `redbus-occupancy@redbus-occupancy.iam.gserviceaccount.com` as Editor.

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Put the service-account JSON at the path in `config/config.ini`:

```ini
[GoogleSheets]
spreadsheet_id = <your spreadsheet id>
worksheet_name = Occupancy Report
return_worksheet_name = Nanded to Pune
credentials_path = config/redbus-occupancy-586ee3125351.json
```

`from_city` and `to_city` are the outbound route. The collector also runs the reverse, `to_city` to `from_city`, and writes that direction to `return_worksheet_name`. Change the city names when the route should change; the return tab name should change with them.

Run the collector. Locally this opens a visible Chromium window because `pytest.ini` includes `--headed`.

```bash
pytest testcases/test_route_occupancy.py
```

Rows are appended to those two tabs. The run does not create a new spreadsheet.

## GitHub Actions

The workflow file is `.github/workflows/occupancy-report.yml`.

- **Schedule:** 11:45 UTC (17:15 IST), every day.
- **Manual run:** Actions tab → Daily occupancy report → Run workflow.
- **Browser:** headless Chromium. The workflow replaces the local `--headed` option.
- **Secret:** `GOOGLE_SERVICE_ACCOUNT_JSON`, the full contents of the service-account JSON file. The workflow writes that secret to `config/redbus-occupancy-586ee3125351.json` for the job and does not store the key in the repository.
- **Sheet:** `spreadsheet_id` and `worksheet_name` are read from `config/config.ini`.
- **Failures:** screenshots, traces, and Allure results are uploaded as the `occupancy-run` artifact.

### Deploy the Action

1. Create a GitHub repository and push this project. Confirm `config/*.json` is not in the commit. `config/config.ini` should be committed so the Action can read the spreadsheet id and route.
2. On GitHub, open **Settings → Secrets and variables → Actions → New repository secret**.
3. Name the secret `GOOGLE_SERVICE_ACCOUNT_JSON`.
4. Paste the entire service-account JSON file, including the `{` and `}`, and save it.
5. Open the spreadsheet, click **Share**, and add `redbus-occupancy@redbus-occupancy.iam.gserviceaccount.com` as **Editor**. Turn off the notify checkbox.
6. Open the **Actions** tab. If GitHub asks to enable Actions for the repository, enable them.
7. Select **Daily occupancy report**, then **Run workflow**. The first run confirms the secret, the browser, and the sheet write.
8. After a run, open the Google Sheet. New buses are new rows under the existing header. A failed run keeps its screenshots under that run’s **Artifacts**.

The schedule starts working after the workflow file is on the repository’s default branch. GitHub may delay a scheduled run by a few minutes. To change the time, edit the `cron` line in `.github/workflows/occupancy-report.yml`. The clock is UTC.
