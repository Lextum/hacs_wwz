"""DataUpdateCoordinator for WWZ Energy."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WwzApiClient, WwzApiError

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)
CET = ZoneInfo("Europe/Zurich")


class WwzEnergyCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch WWZ energy data."""

    def __init__(
        self, hass: HomeAssistant, api_client: WwzApiClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="WWZ Energy",
            update_interval=UPDATE_INTERVAL,
        )
        self.api_client = api_client

    async def _async_update_data(self) -> dict:
        """Fetch energy data from the API.

        Tries today first; if no valid readings yet, falls back to yesterday.
        """
        meter_id = self.api_client.meter_id
        if not meter_id:
            raise UpdateFailed("No meter ID available")

        now = datetime.now(tz=CET)

        try:
            data = await self.api_client.get_daily_data(meter_id, date=now)
        except WwzApiError as err:
            raise UpdateFailed(f"Error fetching WWZ data: {err}") from err

        valid_values = [v for v in data.get("values", []) if v.get("status") == 0]

        # If today has no valid data yet, fetch yesterday instead
        if not valid_values:
            _LOGGER.debug("No valid data for today, falling back to yesterday")
            yesterday = now - timedelta(days=1)
            try:
                data = await self.api_client.get_daily_data(meter_id, date=yesterday)
            except WwzApiError as err:
                raise UpdateFailed(f"Error fetching yesterday's data: {err}") from err
            valid_values = [v for v in data.get("values", []) if v.get("status") == 0]

        # Recalculate daily_total from valid values only
        daily_total = sum(v.get("value", 0) for v in valid_values)
        data["daily_total"] = round(daily_total, 3)

        # Last hour with actual data
        now_ms = int(now.timestamp() * 1000)
        last_hour_value = None
        for v in reversed(valid_values):
            if v.get("date", 0) <= now_ms:
                last_hour_value = v.get("value", 0)
                break

        data["last_hour"] = last_hour_value
        return data
