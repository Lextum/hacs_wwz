<p align="center">
  <img src="custom_components/wwz_energy/brand/icon.png" alt="WWZ Energy" width="128">
</p>

<p align="center">
  A Home Assistant custom integration that fetches energy consumption data from <a href="https://www.wwz.ch/">WWZ</a> smart meters via the WWZ customer portal API.
</p>

## Features

- Energy dashboard integration with hourly statistics
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

The meter ID is discovered automatically during setup.

The lookback period can be changed later under **Devices & Services** > **WWZ Energy** > **Configure**.

## Energy Dashboard

The integration records hourly energy statistics that can be used directly in the Home Assistant **Energy Dashboard**:

1. Go to **Settings** > **Dashboards** > **Energy**
2. Under **Electricity grid**, click **Add consumption**
3. Select the WWZ energy statistic

Data is updated every hour and backfilled for the configured lookback period.

