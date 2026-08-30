# 💡 Ambient Light Sync

Real-time Bluetooth Ambient Lighting sync application for smart LED lights (ELK-BLEDOM / Triones / Zengge). Captures screen colors dynamically using browser Web Media APIs and controls BLE lights in real-time.

## Features
- **Foreground Server Mode**: Stays alive as a server supervisor process.
- **Graceful Shutdown**: Intercepts `Ctrl+C` (`SIGINT`) to cleanly stop all Python server and Chrome browser processes.
- **Automatic BLE Reconnection**: Scans for smart light (`BE:69:D2:13:AA:00`) and automatically retries connection every 3–5 seconds if disconnected or out of range.
- **Real-Time Browser Sync**: Captures screen colors via HTML canvas + WebSockets and streams them to the Bluetooth controller.

## Setup & Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running
```bash
./run.sh
```
Press `Ctrl+C` at any time in the terminal to stop the server and close browser processes.
