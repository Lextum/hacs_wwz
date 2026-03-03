"""The WWZ Energy integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WwzApiClient
from .const import (
    CONF_ENERGY_TARIFF,
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

PLATFORMS = [Platform.SENSOR]

TARIFF_UPDATE_INTERVAL = timedelta(hours=24)


class WwzTariffCoordinator(DataUpdateCoordinator[TariffData | None]):
    """Coordinator that caches WWZ tariff data, refetching only on year rollover."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="WWZ Tariff",
            update_interval=TARIFF_UPDATE_INTERVAL,
        )
        self._cached: TariffData | None = None

    async def _async_update_data(self) -> TariffData | None:
        current_year = datetime.now(tz=ZoneInfo("Europe/Zurich")).year

        if self._cached is not None:
            try:
                if self._cached.year == current_year:
                    return self._cached
            except ValueError:
                pass

        async with aiohttp.ClientSession() as session:
            try:
                self._cached = await fetch_tariff_data(session, current_year)
                return self._cached
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    _LOGGER.debug(
                        "Tariff %d not found, falling back to %d",
                        current_year,
                        current_year - 1,
                    )
                    try:
                        self._cached = await fetch_tariff_data(
                            session, current_year - 1
                        )
                        return self._cached
                    except aiohttp.ClientError:
                        pass
                raise UpdateFailed(
                    f"Failed to fetch tariff data: {err}"
                ) from err
            except aiohttp.ClientError as err:
                raise UpdateFailed(
                    f"Connection error fetching tariffs: {err}"
                ) from err


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry from v1 to v2."""
    if entry.version < 2:
        _LOGGER.debug("Migrating config entry from version %s to 2", entry.version)
        new_options = dict(entry.options)
        new_options.setdefault(CONF_ENERGY_TARIFF, DEFAULT_ENERGY_TARIFF)
        new_options.setdefault(CONF_GRID_TARIFF, DEFAULT_GRID_TARIFF)
        new_options.setdefault(CONF_MUNICIPALITY, "")
        hass.config_entries.async_update_entry(
            entry, options=new_options, version=2
        )
        _LOGGER.debug("Migration to version 2 complete")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WWZ Energy from a config entry."""
    client = WwzApiClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    await client.login()

    lookback_days = entry.options.get(
        CONF_LOOKBACK_DAYS,
        entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
    )

    energy_coordinator = WwzEnergyCoordinator(hass, client, lookback_days)
    await energy_coordinator.async_config_entry_first_refresh()

    tariff_coordinator = WwzTariffCoordinator(hass)
    await tariff_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "energy_coordinator": energy_coordinator,
        "tariff_coordinator": tariff_coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["energy_coordinator"].api_client.close()
    return unload_ok
