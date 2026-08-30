import asyncio
import json
import random
import sys
import websockets
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

MAC_ADDRESS = "BE:69:D2:13:AA:00"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

connected_websockets = set()
current_status = {"connected": False, "device_name": "OA10_36", "mac": MAC_ADDRESS, "error": "Initializing"}

# The ELK-BLEDOM v2 command that worked for your light
def create_elk2_command(r, g, b):
    return bytearray([0x7e, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xef])

def save_status_file(is_connected, error_msg=None):
    try:
        with open("status.json", "w") as f:
            json.dump({
                "connected": is_connected,
                "device_name": "OA10_36",
                "mac": MAC_ADDRESS,
                "mode": "screen",
                "error": error_msg
            }, f)
    except Exception:
        pass

async def broadcast_status(is_connected, error_msg=None):
    current_status["connected"] = is_connected
    current_status["error"] = error_msg
    save_status_file(is_connected, error_msg)

    status_data = json.dumps({
        "type": "status",
        "connected": is_connected,
        "mac": MAC_ADDRESS,
        "error": error_msg
    })

    if connected_websockets:
        to_remove = set()
        for ws in connected_websockets:
            try:
                await ws.send(status_data)
            except Exception:
                to_remove.add(ws)
        connected_websockets.difference_update(to_remove)

async def bluetooth_loop(color_queue):
    print(f"🔍 Checking Smart Light Bluetooth Connection ({MAC_ADDRESS})...", flush=True)
    while True:
        try:
            device = await BleakScanner.find_device_by_address(MAC_ADDRESS, timeout=4.0)
            
            if not device:
                wait_sec = round(random.uniform(3.0, 5.0), 1)
                print(f"💡 Light Status: ⚠️ NOT CONNECTED. Retrying connection in {wait_sec} seconds...", flush=True)
                await broadcast_status(False, "Device not found")
                await asyncio.sleep(wait_sec)
                continue

            print(f"[Bluetooth] Found light! Connecting to {MAC_ADDRESS}...", flush=True)
            async with BleakClient(device, timeout=10.0) as client:
                print(f"💡 Light Status: ✅ CONNECTED & READY (OA10_36 / {MAC_ADDRESS})", flush=True)
                await broadcast_status(True, None)
                
                while True:
                    try:
                        r, g, b = await asyncio.wait_for(color_queue.get(), timeout=2.0)
                        if not client.is_connected:
                            raise BleakError("Connection to light was lost")
                        cmd = create_elk2_command(r, g, b)
                        await client.write_gatt_char(WRITE_UUID, cmd, response=False)
                    except asyncio.TimeoutError:
                        if not client.is_connected:
                            raise BleakError("Connection to light was lost")
                    
        except BleakError as e:
            wait_sec = round(random.uniform(3.0, 5.0), 1)
            print(f"💡 Light Status: ⚠️ NOT CONNECTED ({e}). Retrying in {wait_sec} seconds...", flush=True)
            await broadcast_status(False, str(e))
            await asyncio.sleep(wait_sec)
        except asyncio.CancelledError:
            print("[Bluetooth] Stopping Bluetooth connection loop...", flush=True)
            break
        except Exception as e:
            wait_sec = round(random.uniform(3.0, 5.0), 1)
            print(f"💡 Light Status: ⚠️ NOT CONNECTED ({e}). Retrying in {wait_sec} seconds...", flush=True)
            await broadcast_status(False, str(e))
            await asyncio.sleep(wait_sec)

async def websocket_handler(websocket, color_queue):
    print("[WebSocket] Browser connected! Syncing started.", flush=True)
    connected_websockets.add(websocket)
    
    # Send initial status to browser
    try:
        await websocket.send(json.dumps({
            "type": "status",
            "connected": current_status["connected"],
            "mac": MAC_ADDRESS,
            "error": current_status["error"]
        }))
    except Exception:
        pass

    try:
        async for message in websocket:
            data = json.loads(message)
            if color_queue.full():
                try:
                    color_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            color_queue.put_nowait((data['r'], data['g'], data['b']))
    except websockets.exceptions.ConnectionClosed:
        print("[WebSocket] Browser disconnected.", flush=True)
    finally:
        connected_websockets.discard(websocket)

async def main():
    color_queue = asyncio.Queue(maxsize=1)
    
    bt_task = asyncio.create_task(bluetooth_loop(color_queue))
    
    server = await websockets.serve(
        lambda ws: websocket_handler(ws, color_queue), 
        "localhost", 8765
    )
    print("⚙️ Ambient Light Server running (Port 8765)", flush=True)
    
    try:
        await asyncio.gather(bt_task, server.wait_closed())
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.", flush=True)
        sys.exit(0)
