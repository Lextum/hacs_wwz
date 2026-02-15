"""Sensor platform for WWZ Energy."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_METER_ID, DOMAIN
from .coordinator import WwzEnergyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WWZ Energy sensors from a config entry."""
    coordinator: WwzEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    meter_id = entry.data[CONF_METER_ID]

    async_add_entities([WwzDailyEnergySensor(coordinator, meter_id)])


class WwzDailyEnergySensor(CoordinatorEntity[WwzEnergyCoordinator], SensorEntity):
    """Sensor for daily energy consumption from WWZ."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_has_entity_name = True
    _attr_name = "Daily energy"
    _attr_icon = "mdi:lightning-bolt"

    def __init__(
        self, coordinator: WwzEnergyCoordinator, meter_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._attr_unique_id = f"wwz_energy_{meter_id}_daily"

    @property
    def native_value(self) -> float | None:
        """Return today's total energy consumption."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("daily_total")

    @property
    def last_reset(self) -> datetime:
        """Return the start of today as the last reset time."""
        cet = ZoneInfo("Europe/Zurich")
        now = datetime.now(tz=cet)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
