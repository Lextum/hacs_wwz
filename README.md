<p align="center">
  <img src="custom_components/wwz_energy/brand/icon.png" alt="WWZ Energy" width="128">
</p>

<p align="center">
  A Home Assistant custom integration that fetches energy consumption data from <a href="https://www.wwz.ch/">WWZ</a> smart meters via the WWZ customer portal API.
</p>

> **Disclaimer:** This is an unofficial community project and is not affiliated with, endorsed by, or connected to WWZ AG in any way.

## Features

- Energy dashboard integration with hourly consumption statistics
- Optional cost tracking based on published WWZ tariffs
- Configurable tariff selection (energy product, grid tariff, municipality)
- Configurable lookback period (1–365 days, default: 2 days)
- Automatic session management and re-authentication
- Automatic meter ID discovery
- Configurable via the Home Assistant UI

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** > three-dot menu > **Custom repositories**
3. Add `Lextum/hacs_wwz` with category **Integration**
4. Search for "WWZ Energy" and install it
5. Restart Home Assistant

### Manual

Copy the `custom_components/wwz_energy` folder into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **WWZ Energy**
3. Enter your WWZ portal credentials (email and password)
4. Optionally adjust the lookback period (how many days of historical data to fetch)
5. Optionally enable **Cost Tracking** to calculate energy costs based on your tariff
6. If cost tracking is enabled, select your energy product, grid tariff, and municipality

The meter ID is discovered automatically during setup.

All options can be changed later under **Devices & Services** > **WWZ Energy** > **Configure**.

## Energy Dashboard

The integration records hourly statistics that can be used directly in the Home Assistant **Energy Dashboard**:

1. Go to **Settings** > **Dashboards** > **Energy**
2. Under **Electricity grid**, click **Add consumption**
3. Select the WWZ energy consumption statistic
4. If cost tracking is enabled, select the WWZ energy cost statistic under **Use an entity tracking the total costs**

Data is updated every hour and backfilled for the configured lookback period.

