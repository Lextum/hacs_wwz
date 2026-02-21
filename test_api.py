"""Quick standalone test for the WWZ API client."""

import asyncio
import logging
import sys
from datetime import datetime

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
        today = datetime.now(tz=ZoneInfo("Europe/Zurich")) - timedelta(days=0)
        
        data = await client.get_hourly_data(meter_id, from_date=yesterday, to_date=today)
        print(f"Unit: {data['unit']}")
        print(f"Hourly values ({len(data['values'])} entries):")
        
        for v in data["values"]:
            dt = datetime.fromtimestamp(v["date"] / 1000, tz=ZoneInfo("Europe/Zurich"))
            print(f"  {dt.strftime('%Y-%m-%d %H:%M')} -> {v['value']} kWh (status: {v['status']})")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
    finally:
        await client.close()


asyncio.run(main())
