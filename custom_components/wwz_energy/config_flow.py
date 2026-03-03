"""Config flow for WWZ Energy."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .api import WwzApiClient, WwzApiError, WwzAuthError
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
from .tariff import TariffData, fetch_tariff_data

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_LOOKBACK_DAYS, default=DEFAULT_LOOKBACK_DAYS): vol.All(
            int, vol.Range(min=1, max=365)
        ),
    }
)

NONE_MUNICIPALITY = "none"


async def _fetch_tariff_or_none() -> TariffData | None:
    """Fetch current-year tariff data, returning None on failure."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    year = datetime.now(tz=ZoneInfo("Europe/Zurich")).year
    async with aiohttp.ClientSession() as session:
        try:
            return await fetch_tariff_data(session, year)
        except aiohttp.ClientResponseError:
            try:
                return await fetch_tariff_data(session, year - 1)
            except aiohttp.ClientResponseError:
                return None
        except aiohttp.ClientError:
            return None


def _build_tariff_schema(
    tariff_data: TariffData,
    default_energy: str = DEFAULT_ENERGY_TARIFF,
    default_grid: str = DEFAULT_GRID_TARIFF,
    default_municipality: str = "",
) -> vol.Schema:
    """Build a voluptuous schema with tariff dropdown options."""
    energy_names = tariff_data.energy_product_names()
    grid_names = tariff_data.grid_tariff_names()
    municipality_names = tariff_data.municipality_names()

    if default_energy not in energy_names and energy_names:
        default_energy = energy_names[0]
    if default_grid not in grid_names and grid_names:
        default_grid = grid_names[0]

    muni_options = [NONE_MUNICIPALITY] + municipality_names
    default_muni = default_municipality if default_municipality in municipality_names else NONE_MUNICIPALITY

    return vol.Schema(
        {
            vol.Required(CONF_ENERGY_TARIFF, default=default_energy): vol.In(
                energy_names
            ),
            vol.Required(CONF_GRID_TARIFF, default=default_grid): vol.In(
                grid_names
            ),
            vol.Optional(CONF_MUNICIPALITY, default=default_muni): vol.In(
                muni_options
            ),
        }
    )


class WwzEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WWZ Energy."""

    VERSION = 2

    def __init__(self) -> None:
        super().__init__()
        self._user_data: dict[str, Any] = {}
        self._meter_id: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WwzEnergyOptionsFlow:
        """Get the options flow."""
        return WwzEnergyOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = WwzApiClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            try:
                await client.login()
            except WwzAuthError:
                errors["base"] = "invalid_auth"
            except WwzApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                self._meter_id = client.meter_id
                self._user_data = user_input
                return await self.async_step_tariff()
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_tariff(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle tariff selection step."""
        if user_input is not None:
            municipality = user_input.get(CONF_MUNICIPALITY, "")
            if municipality == NONE_MUNICIPALITY:
                municipality = ""

            await self.async_set_unique_id(f"wwz_energy_{self._meter_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"WWZ Meter {self._meter_id}",
                data=self._user_data,
                options={
                    CONF_ENERGY_TARIFF: user_input[CONF_ENERGY_TARIFF],
                    CONF_GRID_TARIFF: user_input[CONF_GRID_TARIFF],
                    CONF_MUNICIPALITY: municipality,
                },
            )

        tariff_data = await _fetch_tariff_or_none()
        if tariff_data is None:
            # Cannot fetch tariffs — create entry with defaults
            await self.async_set_unique_id(f"wwz_energy_{self._meter_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"WWZ Meter {self._meter_id}",
                data=self._user_data,
                options={
                    CONF_ENERGY_TARIFF: DEFAULT_ENERGY_TARIFF,
                    CONF_GRID_TARIFF: DEFAULT_GRID_TARIFF,
                    CONF_MUNICIPALITY: "",
                },
            )

        return self.async_show_form(
            step_id="tariff",
            data_schema=_build_tariff_schema(tariff_data),
        )


class WwzEnergyOptionsFlow(OptionsFlow):
    """Handle options for WWZ Energy."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            municipality = user_input.get(CONF_MUNICIPALITY, "")
            if municipality == NONE_MUNICIPALITY:
                municipality = ""
            data = {
                CONF_LOOKBACK_DAYS: user_input[CONF_LOOKBACK_DAYS],
                CONF_ENERGY_TARIFF: user_input.get(
                    CONF_ENERGY_TARIFF,
                    self.config_entry.options.get(CONF_ENERGY_TARIFF, DEFAULT_ENERGY_TARIFF),
                ),
                CONF_GRID_TARIFF: user_input.get(
                    CONF_GRID_TARIFF,
                    self.config_entry.options.get(CONF_GRID_TARIFF, DEFAULT_GRID_TARIFF),
                ),
                CONF_MUNICIPALITY: municipality or self.config_entry.options.get(CONF_MUNICIPALITY, ""),
            }
            return self.async_create_entry(title="", data=data)

        current_lookback = self.config_entry.options.get(
            CONF_LOOKBACK_DAYS,
            self.config_entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
        )
        current_energy = self.config_entry.options.get(
            CONF_ENERGY_TARIFF, DEFAULT_ENERGY_TARIFF
        )
        current_grid = self.config_entry.options.get(
            CONF_GRID_TARIFF, DEFAULT_GRID_TARIFF
        )
        current_municipality = self.config_entry.options.get(CONF_MUNICIPALITY, "")

        tariff_data = await _fetch_tariff_or_none()

        if tariff_data is not None:
            tariff_schema = _build_tariff_schema(
                tariff_data, current_energy, current_grid, current_municipality
            )
            # Merge lookback into tariff schema fields
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_LOOKBACK_DAYS, default=current_lookback
                    ): vol.All(int, vol.Range(min=1, max=365)),
                    **tariff_schema.schema,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_LOOKBACK_DAYS, default=current_lookback
                    ): vol.All(int, vol.Range(min=1, max=365)),
                }
            )

        return self.async_show_form(step_id="init", data_schema=schema)
