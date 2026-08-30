import asyncio
from bleak import BleakScanner

MAC_ADDRESS = "BE:69:D2:13:AA:00"

async def check():
    try:
        device = await BleakScanner.find_device_by_address(MAC_ADDRESS, timeout=3.0)
        if device:
            print("CONNECTED")
        else:
            print("NOT_CONNECTED")
    except Exception:
        print("NOT_CONNECTED")

if __name__ == "__main__":
    asyncio.run(check())
