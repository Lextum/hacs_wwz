"""Quick standalone test for the WWZ API client."""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.DEBUG)

# Import directly rather than through HA
sys.path.insert(0, "custom_components")

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from wwz_energy.api import WwzApiClient


async def main():
    username = input("Email: ")
    password = input("Password: ")

    client = WwzApiClient(username, password)

    try:
        print("\n--- Login ---")
        await client.login()
        print(f"Login OK, discovered meter_id: {client.meter_id}")

        meter_id = client.meter_id
        if not meter_id:
            print("ERROR: No meter ID discovered")
            return

        # Fetch yesterday's data (today may not have data yet)
        yesterday = datetime.now(tz=ZoneInfo("Europe/Zurich")) - timedelta(days=1)
        print(f"\n--- Fetch data for {yesterday.date()} ---")
        data = await client.get_daily_data(meter_id, date=yesterday)
        print(f"Unit: {data['unit']}")
        print(f"Daily total: {data['daily_total']} kWh")
        print(f"Hourly values ({len(data['values'])} entries):")
        for v in data["values"]:
            print(f"  {v['date']} -> {v['value']} kWh (status: {v['status']})")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
    finally:
        await client.close()


asyncio.run(main())
