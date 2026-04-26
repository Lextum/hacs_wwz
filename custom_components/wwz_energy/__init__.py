"""The WWZ Energy integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WwzApiClient, WwzApiError, WwzAuthError
from .const import (
    CONF_ENABLE_PRICE_SENSOR,
    CONF_ENERGY_TARIFF,
    CONF_FULL_DAYS_ONLY,
    CONF_GRID_TARIFF,
    CONF_LOOKBACK_DAYS,
    CONF_MUNICIPALITY,
    DEFAULT_ENERGY_TARIFF,
    DEFAULT_GRID_TARIFF,
    DEFAULT_LOOKBACK_DAYS,
    DOMAIN,
)
from .coordinator import WwzEnergyCoordinator
from .tariff import TariffData, fetch_tariff_data

_LOGGER = logging.getLogger(__name__)

TARIFF_UPDATE_INTERVAL = timedelta(hours=24)


class WwzTariffCoordinator(DataUpdateCoordinator[dict[int, TariffData]]):
    """Coordinator that caches WWZ tariff data per year."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="WWZ Tariff",
            update_interval=TARIFF_UPDATE_INTERVAL,
        )
        self._cached: dict[int, TariffData] = {}

    async def _async_update_data(self) -> dict[int, TariffData]:
        current_year = datetime.now(tz=ZoneInfo("Europe/Zurich")).year
        years_needed = [current_year - 1, current_year]

        async with aiohttp.ClientSession() as session:
            for year in years_needed:
                if year in self._cached:
                    continue
                try:
                    self._cached[year] = await fetch_tariff_data(session, year)
                except aiohttp.ClientResponseError as err:
                    if err.status == 404:
                        _LOGGER.debug("Tariff %d not available", year)
                    else:
                        raise UpdateFailed(
                            f"Failed to fetch tariff data: {err}"
                        ) from err
                except aiohttp.ClientError as err:
                    raise UpdateFailed(
                        f"Connection error fetching tariffs: {err}"
                    ) from err

        return {y: t for y, t in self._cached.items() if y in years_needed}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WWZ Energy from a config entry."""
    client = WwzApiClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    try:
        await client.login()
    except WwzAuthError as err:
        await client.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except WwzApiError as err:
        await client.close()
        raise ConfigEntryNotReady(f"WWZ portal unavailable: {err}") from err
    except Exception:
        await client.close()
        raise

    lookback_days = entry.options.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS)
    full_days_only = entry.options.get(CONF_FULL_DAYS_ONLY, False)

    energy_coordinator = WwzEnergyCoordinator(
        hass, client, entry.unique_id, lookback_days, full_days_only
    )

    entry_data: dict[str, Any] = {
        "energy_coordinator": energy_coordinator,
        "tariff_coordinator": None,
    }

    if entry.options.get(CONF_ENABLE_PRICE_SENSOR, False):
        tariff_coordinator = WwzTariffCoordinator(hass)
        await tariff_coordinator.async_config_entry_first_refresh()
        entry_data["tariff_coordinator"] = tariff_coordinator

        tariff_by_year = tariff_coordinator.data
        if tariff_by_year:
            energy_tariff = entry.options.get(CONF_ENERGY_TARIFF, DEFAULT_ENERGY_TARIFF)
            grid_tariff = entry.options.get(CONF_GRID_TARIFF, DEFAULT_GRID_TARIFF)
            municipality = entry.options.get(CONF_MUNICIPALITY, "")
            for year, td in tariff_by_year.items():
                price = td.calculate_total_price(energy_tariff, grid_tariff, municipality)
                if price:
                    energy_coordinator.price_per_kwh_by_year[year] = price
            _LOGGER.debug(
                "Set price_per_kwh_by_year=%s on energy coordinator",
                energy_coordinator.price_per_kwh_by_year,
            )

    try:
        await energy_coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry_data

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data:
        await data["energy_coordinator"].api_client.close()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up statistics when the config entry is removed."""
    from homeassistant.helpers.recorder import get_instance

    from .util import statistic_ids_for_entry

    statistic_ids = list(statistic_ids_for_entry(entry.unique_id or ""))
    get_instance(hass).async_clear_statistics(statistic_ids)
