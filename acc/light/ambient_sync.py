import asyncio
import time
import numpy as np
from mss import mss
from PIL import Image
from bleak import BleakClient, BleakScanner

# Configuration
MAC_ADDRESS = "BE:69:D2:13:AA:00"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
FPS = 10  # How many times per second to update the light

# Protocol mapping based on the test
def create_elk_command(r, g, b):
    return bytearray([0x7e, 0x07, 0x05, 0x03, r, g, b, 0x10, 0xef])

def create_elk2_command(r, g, b):
    return bytearray([0x7e, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xef])

def create_triones_command(r, g, b):
    return bytearray([0x56, r, g, b, 0x00, 0xf0, 0xaa])

def create_zengge_command(r, g, b):
    return bytearray([0x31, r, g, b, 0x00, 0x00, 0x0f])

# --- Set this to the command that worked for your light! ---
CREATE_CMD = create_elk2_command

def get_dominant_color():
    with mss() as sct:
        # Capture the primary monitor
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        
        # Convert to PIL Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        # Resize aggressively to average the colors out quickly and downscale
        img = img.resize((64, 64), resample=Image.Resampling.BILINEAR)
        
        # Convert to numpy array of RGB pixels
        pixels = np.array(img).reshape(-1, 3)
        
        # Filter out very dark pixels (e.g. letterboxing and shadows)
        # Sum of R, G, B > threshold
        bright_pixels = pixels[pixels.sum(axis=1) > 30]
        
        if len(bright_pixels) == 0:
            return 0, 0, 0
            
        # Average the remaining bright pixels
        avg_rgb = bright_pixels.mean(axis=0)
        r, g, b = int(avg_rgb[0]), int(avg_rgb[1]), int(avg_rgb[2])
        
        # Boost brightness dynamically so the LED is vibrant even in dark scenes
        max_val = max(r, g, b)
        if max_val > 0:
            # Scale so the brightest channel is at least 180 (for a vibrant light)
            scale = max(1.0, 180 / max_val)
            r = min(255, int(r * scale))
            g = min(255, int(g * scale))
            b = min(255, int(b * scale))
            
        return r, g, b

async def main():
    print(f"Starting ambient sync. Looking for {MAC_ADDRESS}...")
    
    while True:
        try:
            device = await BleakScanner.find_device_by_address(MAC_ADDRESS, timeout=10.0)
            
            if not device:
                print("Device not found. Retrying in 5 seconds...")
                await asyncio.sleep(5)
                continue

            async with BleakClient(device) as client:
                print("Connected! Starting ambient sync. Press Ctrl+C to stop.")
                
                while True:
                    start_time = time.time()
                    
                    r, g, b = get_dominant_color()
                    print(f"Captured color: R={r}, G={g}, B={b}")
                    cmd = CREATE_CMD(r, g, b)
                    await client.write_gatt_char(WRITE_UUID, cmd, response=False)
                    
                    elapsed = time.time() - start_time
                    sleep_time = max(0, (1.0 / FPS) - elapsed)
                    await asyncio.sleep(sleep_time)
                    
        except BleakError as e:
            print(f"Bluetooth error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            print("\nStopping ambient sync...")
            break
        except KeyboardInterrupt:
            print("\nStopping ambient sync...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    from bleak.exc import BleakError
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
