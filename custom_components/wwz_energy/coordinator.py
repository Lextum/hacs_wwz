"""DataUpdateCoordinator for WWZ Energy."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.models import StatisticData, StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.recorder import get_instance
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WwzApiClient, WwzApiError

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)
CET = ZoneInfo("Europe/Zurich")


class WwzEnergyCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch WWZ energy data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: WwzApiClient,
        entry_unique_id: str,
        lookback_days: int = 2,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="WWZ Energy",
            update_interval=UPDATE_INTERVAL,
        )
        self.api_client = api_client
        self.lookback_days = lookback_days
        slug = re.sub(r"[^a-z0-9]", "_", entry_unique_id.lower()).strip("_")
        self.energy_statistic_id = f"wwz_energy:{slug}_energy_consumption"
        self.cost_statistic_id = f"wwz_energy:{slug}_energy_cost"
        self.price_per_kwh_by_year: dict[int, float] = {}

    async def _async_update_data(self) -> dict:
        """Fetch energy data and write external statistics for consumption and cost."""
        meter_id = self.api_client.meter_id
        if not meter_id:
            raise UpdateFailed("No meter ID available")

        now = datetime.now(tz=CET)
        from_date = await self._get_fetch_start(now)

        try:
            data = await self.api_client.get_hourly_data(meter_id, from_date=from_date, to_date=now)
        except WwzApiError as err:
            raise UpdateFailed(f"Error fetching WWZ data: {err}") from err

        # Filter valid values and deduplicate by timestamp (prefer status=0)
        seen: dict[int, dict] = {}
        for v in data.get("values", []):
            if v.get("status") == 0 or (v.get("status") == 3 and v.get("value", 0) > 0):
                ts = v["date"]
                if ts not in seen or v.get("status") == 0:
                    seen[ts] = v

        sorted_values = sorted(seen.values(), key=lambda x: x["date"])

        _LOGGER.debug(
            "%d valid values out of %d total",
            len(sorted_values),
            len(data.get("values", [])),
        )

        if sorted_values:
            await self._insert_statistics(sorted_values, from_date)

        return data

    async def _get_fetch_start(self, now: datetime) -> datetime:
        """Determine the start of the fetch window.

        If we already have statistics recorded, fetch only from the last known
        hour (minus a small overlap buffer) instead of the full lookback window.
        Falls back to lookback_days on first run or if the recorder query fails.
        """
        fallback = now - timedelta(days=self.lookback_days)
        try:
            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, self.energy_statistic_id, False, {"start"}
            )
        except Exception:
            _LOGGER.debug("Could not query recorder for last statistic, using full lookback")
            return fallback

        if not last_stat or self.energy_statistic_id not in last_stat:
            _LOGGER.debug("No existing statistics found, using full lookback")
            return fallback

        # start is a UTC epoch float (seconds) from the recorder DB
        last_start = last_stat[self.energy_statistic_id][0]["start"]
        last_dt = datetime.fromtimestamp(last_start, tz=CET)
        fetch_from = last_dt - timedelta(hours=2)
        _LOGGER.debug(
            "Last statistic at %s, fetching from %s (saved ~%d hours)",
            last_dt.isoformat(),
            fetch_from.isoformat(),
            max(0, int((fetch_from - fallback).total_seconds() / 3600)),
        )
        return fetch_from

    async def _get_last_sum(
        self, statistic_id: str, fetch_start: datetime
    ) -> tuple[float, float | None]:
        """Return (sum, last_start_ts) from the recorder at fetch_start.

        Returns (0.0, None) when no prior statistics exist.
        """
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                fetch_start,
                None,
                {statistic_id},
                "hour",
                None,
                {"sum"},
            )
        except Exception:
            return 0.0, None

        if not stats or statistic_id not in stats:
            return 0.0, None

        return stats[statistic_id][0]["sum"], stats[statistic_id][0]["start"]

    async def _insert_statistics(self, sorted_values: list[dict], fetch_start: datetime) -> None:
        """Write hourly energy consumption and cost as external statistics."""
        energy_sum, last_energy_ts = await self._get_last_sum(
            self.energy_statistic_id, fetch_start
        )
        cost_sum, last_cost_ts = await self._get_last_sum(
            self.cost_statistic_id, fetch_start
        )

        energy_stats: list[StatisticData] = []
        cost_stats: list[StatisticData] = []

        for v in sorted_values:
            kwh = v.get("value") or 0.0
            dt = datetime.fromtimestamp(v["date"] / 1000, tz=CET).replace(
                minute=0, second=0, microsecond=0
            )
            dt_ts = dt.timestamp()

            # Skip rows already covered by the recorder
            if last_energy_ts is not None and dt_ts <= last_energy_ts:
                continue

            energy_sum = round(energy_sum + kwh, 3)
            energy_stats.append(
                StatisticData(start=dt, state=round(kwh, 3), sum=energy_sum)
            )

            price = self.price_per_kwh_by_year.get(dt.year)
            if price is not None:
                cost = round(kwh * price, 4)
                cost_sum = round(cost_sum + cost, 4)
                cost_stats.append(
                    StatisticData(start=dt, state=cost, sum=cost_sum)
                )

        energy_metadata = StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name="WWZ Energy Consumption",
            source="wwz_energy",
            statistic_id=self.energy_statistic_id,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            unit_class="energy",
        )
        async_add_external_statistics(self.hass, energy_metadata, energy_stats)
        _LOGGER.debug(
            "Inserted %d energy statistics for %s",
            len(energy_stats), self.energy_statistic_id,
        )

        if cost_stats:
            cost_metadata = StatisticMetaData(
                has_mean=False,
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name="WWZ Energy Cost",
                source="wwz_energy",
                statistic_id=self.cost_statistic_id,
                unit_of_measurement="CHF",
                unit_class=None,
            )
            async_add_external_statistics(self.hass, cost_metadata, cost_stats)
            _LOGGER.debug(
                "Inserted %d cost statistics for %s",
                len(cost_stats), self.cost_statistic_id,
            )
