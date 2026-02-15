"""Debug: check what data is available for today vs yesterday."""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "custom_components")

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from wwz_energy.api import WwzApiClient

CET = ZoneInfo("Europe/Zurich")


async def main():
    username = input("Email: ")
    password = input("Password: ")

    client = WwzApiClient(username, password)

    try:
        await client.login()
        meter_id = client.meter_id

        for label, date in [
            ("Today", datetime.now(tz=CET)),
            ("Yesterday", datetime.now(tz=CET) - timedelta(days=1)),
        ]:
            data = await client.get_daily_data(meter_id, date=date)
            valid = [v for v in data["values"] if v["status"] == 0]
            pending = [v for v in data["values"] if v["status"] == 3]
            print(f"\n{label} ({date.date()}):")
            print(f"  Total entries: {len(data['values'])}")
            print(f"  Valid (status=0): {len(valid)}")
            print(f"  Pending (status=3): {len(pending)}")
            print(f"  daily_total: {data['daily_total']} kWh")
            if valid:
                print(f"  Last valid: {valid[-1]}")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
    finally:
        await client.close()


asyncio.run(main())
