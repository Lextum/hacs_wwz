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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WwzApiClient
from .const import (
    CONF_ENABLE_PRICE_SENSOR,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WWZ Energy from a config entry."""
    client = WwzApiClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    try:
        await client.login()
    except Exception:
        await client.close()
        raise

    lookback_days = entry.options.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS)

    energy_coordinator = WwzEnergyCoordinator(hass, client, entry.unique_id, lookback_days)

    entry_data: dict[str, Any] = {
        "energy_coordinator": energy_coordinator,
        "tariff_coordinator": None,
    }

    if entry.options.get(CONF_ENABLE_PRICE_SENSOR, False):
        tariff_coordinator = WwzTariffCoordinator(hass)
        await tariff_coordinator.async_config_entry_first_refresh()
        entry_data["tariff_coordinator"] = tariff_coordinator

        tariff_data = tariff_coordinator.data
        if tariff_data is not None:
            energy_tariff = entry.options.get(CONF_ENERGY_TARIFF, DEFAULT_ENERGY_TARIFF)
            grid_tariff = entry.options.get(CONF_GRID_TARIFF, DEFAULT_GRID_TARIFF)
            municipality = entry.options.get(CONF_MUNICIPALITY, "")
            price = tariff_data.calculate_total_price(energy_tariff, grid_tariff, municipality)
            if price is not None:
                energy_coordinator.price_per_kwh = price
                _LOGGER.debug("Set price_per_kwh=%.4f CHF on energy coordinator", price)

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
