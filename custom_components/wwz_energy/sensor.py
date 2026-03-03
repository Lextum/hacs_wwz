"""WWZ electricity price sensor."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import (
    CONF_ENERGY_TARIFF,
    CONF_GRID_TARIFF,
    CONF_MUNICIPALITY,
    DEFAULT_ENERGY_TARIFF,
    DEFAULT_GRID_TARIFF,
    DOMAIN,
)
from .tariff import TariffData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WWZ price sensor from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["tariff_coordinator"]
    async_add_entities([WwzElectricityPriceSensor(coordinator, entry)])


class WwzElectricityPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the total electricity price in CHF/kWh."""

    _attr_has_entity_name = True
    _attr_translation_key = "electricity_price"
    _attr_native_unit_of_measurement = "CHF/kWh"
    _attr_suggested_display_precision = 4
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[TariffData | None],
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_electricity_price"

    @property
    def _tariff_data(self) -> TariffData | None:
        return self.coordinator.data

    @property
    def _energy_tariff(self) -> str:
        return self._entry.options.get(CONF_ENERGY_TARIFF, DEFAULT_ENERGY_TARIFF)

    @property
    def _grid_tariff(self) -> str:
        return self._entry.options.get(CONF_GRID_TARIFF, DEFAULT_GRID_TARIFF)

    @property
    def _municipality(self) -> str:
        return self._entry.options.get(CONF_MUNICIPALITY, "")

    @property
    def native_value(self) -> float | None:
        if self._tariff_data is None:
            return None
        return self._tariff_data.calculate_total_price(
            self._energy_tariff, self._grid_tariff, self._municipality
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | float] | None:
        if self._tariff_data is None:
            return None
        breakdown = self._tariff_data.get_price_breakdown(
            self._energy_tariff, self._grid_tariff, self._municipality
        )
        return {
            **breakdown,
            "energy_tariff": self._energy_tariff,
            "grid_tariff": self._grid_tariff,
            "municipality": self._municipality,
        }
