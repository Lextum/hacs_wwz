"""DataUpdateCoordinator for WWZ Energy."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WwzApiClient, WwzApiError

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)


class WwzEnergyCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch WWZ energy data."""

    def __init__(
        self, hass: HomeAssistant, api_client: WwzApiClient, meter_id: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="WWZ Energy",
            update_interval=UPDATE_INTERVAL,
        )
        self.api_client = api_client
        self.meter_id = meter_id

    async def _async_update_data(self) -> dict:
        """Fetch today's energy data from the API."""
        try:
            data = await self.api_client.get_daily_data(self.meter_id)
        except WwzApiError as err:
            raise UpdateFailed(f"Error fetching WWZ data: {err}") from err

        return data
