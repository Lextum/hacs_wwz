"""The WWZ Energy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import WwzApiClient
from .const import CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS, DOMAIN
from .coordinator import WwzEnergyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WWZ Energy from a config entry."""
    client = WwzApiClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    await client.login()

    lookback_days = entry.options.get(
        CONF_LOOKBACK_DAYS,
        entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
    )

    coordinator = WwzEnergyCoordinator(hass, client, lookback_days)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: WwzEnergyCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.api_client.close()
    return True
