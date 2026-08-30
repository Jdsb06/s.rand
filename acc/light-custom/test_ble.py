import asyncio
from bleak import BleakClient, BleakScanner

MAC_ADDRESS = "BE:69:D2:13:AA:00"

async def main():
    print(f"Scanning for device with MAC: {MAC_ADDRESS}...")
    device = await BleakScanner.find_device_by_address(MAC_ADDRESS, timeout=10.0)
    
    if not device:
        print("Device not found. Please make sure the light is on and in range.")
        return

    print(f"Found device: {device.name}")
    print("Connecting...")
    
    try:
        async with BleakClient(device) as client:
            print(f"Connected: {client.is_connected}")
            
            # List all services and characteristics
            for service in client.services:
                print(f"[Service] {service.uuid}: {service.description}")
                for char in service.characteristics:
                    print(f"  [Characteristic] {char.uuid}: {char.description} ({','.join(char.properties)})")
    
    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == "__main__":
    asyncio.run(main())
