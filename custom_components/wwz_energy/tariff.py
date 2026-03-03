"""WWZ tariff data fetching and parsing."""

from __future__ import annotations

import logging

import aiohttp

from .const import TARIFF_URL_TEMPLATE

_LOGGER = logging.getLogger(__name__)

RESIDENTIAL_VOLTAGE_LEVEL = 7


class TariffData:
    """Parsed WWZ tariff data for residential customers (NE 7)."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw
        self._tariffs = [
            t for t in raw.get("tariffs", [])
            if t.get("customerVoltageLevel") == RESIDENTIAL_VOLTAGE_LEVEL
        ]

    @property
    def year(self) -> int:
        """Extract tariff year from startDate of first tariff."""
        for t in self._tariffs:
            start = t.get("startDate", "")
            if start:
                return int(start.split("-")[0])
        raise ValueError("No tariffs with startDate found")

    def _by_type(self, tariff_type: str) -> list[dict]:
        return [t for t in self._tariffs if t.get("tariffType") == tariff_type]

    def energy_product_names(self) -> list[str]:
        """Return available energy product names."""
        return [t["tariffName"] for t in self._by_type("electricity")]

    def grid_tariff_names(self) -> list[str]:
        """Return available grid tariff names."""
        return [t["tariffName"] for t in self._by_type("grid")]

    def municipality_names(self) -> list[str]:
        """Return available municipality names from regional fees."""
        names: list[str] = []
        for t in self._by_type("regional_fees"):
            for m in t.get("prices", {}).get("municipalityTaxes", []):
                name = m.get("municipalityName", "")
                if name and name not in names:
                    names.append(name)
        return sorted(names)

    def _get_energy_price(self, tariff_name: str) -> float:
        """Get energy price (CHF/kWh) for a named electricity tariff."""
        for t in self._by_type("electricity"):
            if t["tariffName"] == tariff_name:
                return t["prices"]["energy"][0]["price"]
        return 0.0

    def _get_grid_price(self, tariff_name: str) -> float:
        """Get grid energy price (CHF/kWh) for a named grid tariff."""
        for t in self._by_type("grid"):
            if t["tariffName"] == tariff_name:
                return t["prices"]["energy"][0]["price"]
        return 0.0

    def _get_cantonal_fee(self) -> float:
        """Get cantonal energy fee (CHF/kWh) — sum of all cantonal taxes."""
        total = 0.0
        for t in self._by_type("regional_fees"):
            for c in t.get("prices", {}).get("cantonalTaxes", []):
                for e in c.get("cantonEnergy", []):
                    total += e.get("price", 0.0)
        return total

    def _get_municipality_fee(self, municipality_name: str) -> float:
        """Get municipality energy fee (CHF/kWh) for a named municipality."""
        if not municipality_name:
            return 0.0
        for t in self._by_type("regional_fees"):
            for m in t.get("prices", {}).get("municipalityTaxes", []):
                if m.get("municipalityName") == municipality_name:
                    for e in m.get("municipalityEnergy", []):
                        return e.get("price", 0.0)
        return 0.0

    def calculate_total_price(
        self,
        energy_tariff: str,
        grid_tariff: str,
        municipality: str = "",
    ) -> float:
        """Calculate total electricity price in CHF/kWh."""
        return round(
            self._get_energy_price(energy_tariff)
            + self._get_grid_price(grid_tariff)
            + self._get_cantonal_fee()
            + self._get_municipality_fee(municipality),
            4,
        )

    def get_price_breakdown(
        self,
        energy_tariff: str,
        grid_tariff: str,
        municipality: str = "",
    ) -> dict[str, float]:
        """Return individual price components for sensor attributes."""
        return {
            "energy_price": self._get_energy_price(energy_tariff),
            "grid_price": self._get_grid_price(grid_tariff),
            "cantonal_fee": self._get_cantonal_fee(),
            "municipality_fee": self._get_municipality_fee(municipality),
        }


async def fetch_tariff_data(
    session: aiohttp.ClientSession, year: int
) -> TariffData:
    """Fetch and parse WWZ tariff JSON for a given year.

    Raises aiohttp.ClientResponseError on HTTP errors (e.g. 404).
    """
    url = TARIFF_URL_TEMPLATE.format(year=year)
    _LOGGER.debug("Fetching tariff data from %s", url)
    async with session.get(url) as resp:
        resp.raise_for_status()
        raw = await resp.json(content_type=None)
    return TariffData(raw)
