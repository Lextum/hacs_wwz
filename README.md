# WWZ Energy

A Home Assistant custom integration that fetches daily energy consumption data from [WWZ](https://www.wwz.ch/) smart meters via the WWZ customer portal API.

## Features

- Daily energy consumption sensor (kWh), updated hourly
- Automatic session management and re-authentication
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
3. Enter your WWZ portal credentials (email and password) and your smart meter ID

## Sensor

| Entity | Description | Unit | Update interval |
|---|---|---|---|
| Daily energy | Total energy consumption for the current day | kWh | 1 hour |

The sensor resets at midnight (Europe/Zurich timezone).

## Finding your meter ID

Your meter ID can be found in the [WWZ customer portal](https://portal.wwz.ch/) under your contract/meter details.
