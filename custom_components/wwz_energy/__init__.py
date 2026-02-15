"""The WWZ Energy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .api import WwzApiClient
from .const import CONF_METER_ID, DOMAIN
from .coordinator import WwzEnergyCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WWZ Energy from a config entry."""
    client = WwzApiClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    await client.login()

    coordinator = WwzEnergyCoordinator(
        hass, client, entry.data[CONF_METER_ID]
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: WwzEnergyCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api_client.close()

    return unload_ok
