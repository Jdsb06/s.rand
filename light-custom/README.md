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

## Music-reactive mode (optional)
`music_sync.py` makes the light react to whatever audio is playing: bass / mid / high bands, loudness and beat detection drive the colour. It is a separate script that streams `{r, g, b}` to the existing `ambient_server.py` WebSocket (same as `sync.html`), so the server, the BLE address and the command format are untouched. It needs no new dependencies (numpy, sounddevice and websockets are already in `requirements.txt`).

```bash
./run.sh                                   # server running as usual
python music_sync.py --list-devices        # pick an input
python music_sync.py                       # auto-picks a monitor/loopback input if one exists
python music_sync.py --device "Monitor of" --style pulse --palette fire --brightness 0.8
```
- Styles: `spectrum` (bass/mid/high mapped to a palette), `pulse` (colour jump on every beat), `energy` (hue follows pitch, brightness follows loudness).
- To hear system audio rather than the mic, choose a PulseAudio/PipeWire *Monitor* input (`pactl list short sources | grep monitor`, or set `PULSE_SOURCE=<that name>`).
- Only one source should drive the light at a time, so don't start screen sync in the browser while this is running.
