"""Utility helpers for WWZ Energy."""

import re


def statistic_ids_for_entry(unique_id: str) -> tuple[str, str]:
    """Return (energy_statistic_id, cost_statistic_id) for a config entry."""
    slug = re.sub(r"[^a-z0-9]", "_", unique_id.lower()).strip("_")
    return (
        f"wwz_energy:{slug}_energy_consumption",
        f"wwz_energy:{slug}_energy_cost",
    )
