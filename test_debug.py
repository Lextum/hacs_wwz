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

        now = datetime.now(tz=CET)
        yesterday = now - timedelta(days=1)

        for label, from_date, to_date in [
            ("Today", now, now),
            ("Yesterday", yesterday, yesterday),
        ]:
            data = await client.get_hourly_data(meter_id, from_date=from_date, to_date=to_date)
            values = data.get("values", [])
            valid = [v for v in values if v["status"] == 0]
            pending = [v for v in values if v["status"] == 3]
            print(f"\n{label} ({from_date.date()}):")
            print(f"  Total entries: {len(values)}")
            print(f"  Valid (status=0): {len(valid)}")
            print(f"  Pending (status=3): {len(pending)}")
            print(f"  Sum: {sum(v.get('value', 0) for v in valid)} kWh")
            if valid:
                print(f"  Last valid: {valid[-1]}")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
    finally:
        await client.close()


asyncio.run(main())
