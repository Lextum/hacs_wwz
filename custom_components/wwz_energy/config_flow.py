"""Config flow for WWZ Energy."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .api import WwzApiClient, WwzApiError, WwzAuthError
from .const import CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS, DOMAIN

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


class WwzEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WWZ Energy."""

    VERSION = 1

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
                meter_id = client.meter_id
                await self.async_set_unique_id(f"wwz_energy_{meter_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"WWZ Meter {meter_id}",
                    data=user_input,
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class WwzEnergyOptionsFlow(OptionsFlow):
    """Handle options for WWZ Energy."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_LOOKBACK_DAYS,
            self.config_entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LOOKBACK_DAYS, default=current): vol.All(
                        int, vol.Range(min=1, max=365)
                    ),
                }
            ),
        )
