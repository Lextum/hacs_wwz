"""DataUpdateCoordinator for WWZ Energy."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WwzApiClient, WwzApiError
from .const import DOMAIN

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

        data_date = now

        try:
            data = await self.api_client.get_daily_data(meter_id, date=now)
        except WwzApiError as err:
            raise UpdateFailed(f"Error fetching WWZ data: {err}") from err

        valid_values = [v for v in data.get("values", []) if v.get("status") == 0]

        # If today has no valid data yet, fetch yesterday instead
        if not valid_values:
            _LOGGER.debug("No valid data for today, falling back to yesterday")
            data_date = now - timedelta(days=1)
            try:
                data = await self.api_client.get_daily_data(meter_id, date=data_date)
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
        data["data_date"] = data_date.strftime("%Y-%m-%d")

        await self._insert_statistics(valid_values)

        return data

    async def _insert_statistics(self, values: list[dict]) -> None:
        """Insert backdated hourly statistics into HA recorder.

        Uses async_add_external_statistics (upsert) so repeated calls for the
        same timestamps are safe — existing entries are overwritten with the
        same values, new entries are created at their actual timestamps.
        """
        if not values:
            return

        statistic_id = f"{DOMAIN}:energy_{self.api_client.meter_id}"
        sorted_values = sorted(values, key=lambda x: x["date"])
        first_dt = datetime.fromtimestamp(sorted_values[0]["date"] / 1000, tz=CET).replace(minute=0, second=0, microsecond=0)

        # Find the cumulative sum stored just before our first data point so
        # that today's running total continues from the right baseline.
        preceding = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            first_dt - timedelta(hours=1),
            first_dt,
            {statistic_id},
            "hour",
            None,
            {"sum"},
        )
        entries = preceding.get(statistic_id) or []
        base_sum = float((entries[-1] if entries else {}).get("sum") or 0.0)

        cumulative_sum = base_sum
        statistics = []
        for v in sorted_values:
            cumulative_sum = round(cumulative_sum + (v.get("value") or 0.0), 3)
            dt = datetime.fromtimestamp(v["date"] / 1000, tz=CET).replace(minute=0, second=0, microsecond=0)
            statistics.append(
                StatisticData(
                    start=dt,
                    sum=cumulative_sum,
                    state=round(v.get("value") or 0.0, 3),
                )
            )
            _LOGGER.debug(
                "  stat: %s -> %.3f kWh (sum: %.3f)",
                dt.strftime("%Y-%m-%d %H:%M"),
                v.get("value") or 0.0,
                cumulative_sum,
            )

        metadata = StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name="WWZ Energy",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )
        async_add_external_statistics(self.hass, metadata, statistics)
        _LOGGER.debug(
            "Inserted %d backdated statistics for %s (base_sum=%.3f)",
            len(statistics),
            statistic_id,
            base_sum,
        )
