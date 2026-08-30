import asyncio
from bleak import BleakClient, BleakScanner

MAC_ADDRESS = "BE:69:D2:13:AA:00"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

async def set_color_elk(client, r, g, b):
    # ELK-BLEDOM protocol variant
    command = bytearray([0x7e, 0x07, 0x05, 0x03, r, g, b, 0x10, 0xef])
    print(f"Sending ELK-BLEDOM command: {command.hex()}")
    await client.write_gatt_char(WRITE_UUID, command, response=False)

async def set_color_elk2(client, r, g, b):
    # Another ELK-BLEDOM protocol variant
    command = bytearray([0x7e, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xef])
    print(f"Sending ELK-BLEDOM v2 command: {command.hex()}")
    await client.write_gatt_char(WRITE_UUID, command, response=False)

async def set_color_triones(client, r, g, b):
    # Triones protocol
    command = bytearray([0x56, r, g, b, 0x00, 0xf0, 0xaa])
    print(f"Sending Triones command: {command.hex()}")
    await client.write_gatt_char(WRITE_UUID, command, response=False)

async def set_color_zengge(client, r, g, b):
    # Zengge protocol
    command = bytearray([0x31, r, g, b, 0x00, 0x00, 0x0f])
    print(f"Sending Zengge command: {command.hex()}")
    await client.write_gatt_char(WRITE_UUID, command, response=False)

async def main():
    print(f"Scanning for device with MAC: {MAC_ADDRESS}...")
    device = await BleakScanner.find_device_by_address(MAC_ADDRESS, timeout=10.0)
    
    if not device:
        print("Device not found.")
        return

    async with BleakClient(device) as client:
        print("Connected.")
        
        print("Testing ELK-BLEDOM protocol (RED)...")
        await set_color_elk(client, 255, 0, 0)
        await asyncio.sleep(2)

        print("Testing ELK-BLEDOM v2 protocol (GREEN)...")
        await set_color_elk2(client, 0, 255, 0)
        await asyncio.sleep(2)
        
        print("Testing Triones protocol (BLUE)...")
        await set_color_triones(client, 0, 0, 255)
        await asyncio.sleep(2)
        
        print("Testing Zengge protocol (PURPLE)...")
        await set_color_zengge(client, 255, 0, 255)
        await asyncio.sleep(2)

        print("Finished test. Which protocol changed the colors?")

if __name__ == "__main__":
    asyncio.run(main())
