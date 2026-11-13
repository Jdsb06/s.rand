#!/usr/bin/env python3
"""Music-reactive mode for Ambient Light Sync.

Listens to an audio input (ideally your system's "monitor"/loopback device so it hears whatever
is playing), analyses it (bass / mid / high bands, loudness, beat detection) and streams colours to
the *existing* ambient_server.py over its WebSocket, exactly like sync.html does:

    {"r": 0-255, "g": 0-255, "b": 0-255}  ->  ws://localhost:8765

Nothing in the server, the BLE address or the command format is touched, and it needs no new
dependencies (numpy, sounddevice and websockets are already in requirements.txt).

Usage (server must be running, e.g. via ./run.sh):
    python music_sync.py --list-devices
    python music_sync.py                          # auto-picks a monitor/loopback input if it finds one
    python music_sync.py --device "Monitor of"    # name substring or index
    python music_sync.py --style pulse --palette fire --brightness 0.8

Only one source should drive the light at a time: stop screen sync in the browser (or don't click
"Select Screen to Sync") while this is running.
"""
import argparse
import asyncio
import json
import sys
import time

import numpy as np
import sounddevice as sd
from websockets.asyncio.client import connect

BLOCK = 1024   # samples per audio block (~21 ms at 48 kHz)
WINDOW = 2048  # FFT window (two blocks)

# palette = (bass colour, mid colour, high colour)
PALETTES = {
    "neon":   [(255, 0, 90),  (0, 200, 255),  (150, 0, 255)],
    "fire":   [(255, 30, 0),  (255, 140, 0),  (255, 230, 60)],
    "ocean":  [(0, 40, 255),  (0, 200, 200),  (120, 255, 220)],
    "aurora": [(0, 255, 120), (0, 160, 255),  (190, 60, 255)],
    "party":  [(255, 0, 0),   (0, 255, 0),    (0, 0, 255)],
}
STYLES = ("spectrum", "pulse", "energy")
FLOORS = {"bass": 2e-4, "mid": 1e-4, "high": 4e-5, "level": 4e-3}  # keeps silence dark


class Analyzer:
    """Audio blocks in -> normalised bass/mid/high/level/centroid + beat events out."""

    def __init__(self, sr):
        self.sr = sr
        self.buf = np.zeros(WINDOW, dtype=np.float32)
        self.win = np.hanning(WINDOW).astype(np.float32)
        freqs = np.fft.rfftfreq(WINDOW, 1.0 / sr)
        self.freqs = freqs
        self.bands = {
            "bass": (freqs >= 30) & (freqs < 200),
            "mid": (freqs >= 200) & (freqs < 2500),
            "high": (freqs >= 2500) & (freqs < 12000),
        }
        self.peak = dict(FLOORS)
        self.bass_hist = np.zeros(43)
        self.prev_bass = 0.0
        self.last_beat = 0.0
        self.beat_id = 0
        self.beat_strength = 0.0

    def _norm(self, key, x):
        # fast-attack / slow-decay peak tracker = automatic gain control
        p = max(x, self.peak[key] * 0.9985, FLOORS[key])
        self.peak[key] = p
        return min(1.0, x / p)

    def feed(self, mono, now=None):
        now = time.time() if now is None else now
        self.buf[:-BLOCK] = self.buf[BLOCK:]
        self.buf[-BLOCK:] = mono[:BLOCK]
        spec = np.abs(np.fft.rfft(self.buf * self.win)) / WINDOW
        f = {k: self._norm(k, float(np.sqrt(np.mean(spec[m] ** 2)))) for k, m in self.bands.items()}
        f["level"] = self._norm("level", float(np.sqrt(np.mean(mono ** 2))))
        tot = float(spec[1:].sum())
        if tot > 1e-5:
            cent = float((self.freqs[1:] * spec[1:]).sum() / tot)
            f["centroid"] = float(np.clip(np.log2(max(cent, 100) / 100) / np.log2(80), 0, 1))
        else:
            f["centroid"] = 0.5

        # beat = bass jumps clearly above its own recent average
        bass = f["bass"]
        self.bass_hist[:-1] = self.bass_hist[1:]
        self.bass_hist[-1] = bass
        flux = bass - self.prev_bass
        self.prev_bass = bass
        if (bass > 1.3 * self.bass_hist[:-1].mean() + 0.05 and bass > 0.3 and flux > 0.06
                and now - self.last_beat > 0.22 and f["level"] > 0.15):
            self.last_beat = now
            self.beat_id += 1
            self.beat_strength = min(1.0, 0.5 + bass * 0.5)
        f["beat_id"], f["beat_strength"] = self.beat_id, self.beat_strength
        return f


class Visualizer:
    """Features -> one (r, g, b) per block, in one of three styles."""

    def __init__(self, style, palette, brightness, sensitivity, floor):
        self.style = style
        self.pal = [tuple(c / 255 for c in p) for p in PALETTES[palette]]
        self.brightness = brightness
        self.sens = sensitivity
        self.floor = floor
        self.sm = {"bass": 0.0, "mid": 0.0, "high": 0.0, "level": 0.0}
        self.env = 0.0
        self.beat_seen = 0
        self.beat_idx = 0

    def step(self, f, dt):
        for k in self.sm:
            x = min(1.0, f[k] * self.sens) ** 1.2
            cur = self.sm[k]
            self.sm[k] = cur + (x - cur) * (0.75 if x > cur else 0.2)
        if f["beat_id"] != self.beat_seen:
            self.beat_seen = f["beat_id"]
            self.beat_idx += 1
            self.env = max(self.env, min(1.0, f["beat_strength"] * min(1.5, self.sens)))
        self.env *= 0.86 ** (dt * 30)          # ~same decay regardless of block size

        sm, pal = self.sm, self.pal
        if self.style == "spectrum":
            col = [0.0, 0.0, 0.0]
            for amount, p in zip((sm["bass"], sm["mid"] * 0.9, sm["high"] * 0.9), pal):
                for i in range(3):
                    col[i] += p[i] * amount
            top = max(col)
            if top > 1:
                col = [c / top for c in col]
        elif self.style == "pulse":
            base = pal[self.beat_idx % 3]
            col = [c * max(self.env, sm["level"] * 0.25) for c in base]
        else:  # energy: hue follows pitch, brightness follows loudness
            x = f["centroid"] * 2
            i = min(int(x), 1)
            c = [a + (b - a) * (x - i) for a, b in zip(pal[i], pal[i + 1])]
            v = min(1.0, sm["level"] * 0.85 + self.env * 0.3)
            col = [k * v for k in c]
        col = [max(c, p * self.floor) for c, p in zip(col, pal[0])]
        return tuple(max(0, min(255, int(c * 255 * self.brightness))) for c in col)


# ---------------------------------------------------------------- audio input
def list_devices():
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"{i:3d}  {d['name']}  ({d['max_input_channels']} ch, {int(d['default_samplerate'])} Hz)")


def pick_device(spec):
    devs = [(i, d) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]
    if spec is not None:
        if spec.isdigit():
            return int(spec)
        for i, d in devs:
            if spec.lower() in d["name"].lower():
                return i
        sys.exit(f"No input device matching '{spec}'. Try --list-devices.")
    for key in ("monitor", "loopback", "stereo mix", "what u hear"):
        for i, d in devs:
            if key in d["name"].lower():
                return i
    print("[music_sync] No monitor/loopback input found, using the default input (probably a microphone).\n"
          "  To react to what is playing, pick a monitor device with --device (see --list-devices).",
          file=sys.stderr)
    return None


async def audio_blocks(device):
    """Yield (mono_block, samplerate) from the chosen input device."""
    info = sd.query_devices(device, "input")
    sr = int(info["default_samplerate"])
    ch = max(1, min(2, info["max_input_channels"]))
    loop = asyncio.get_running_loop()
    q = asyncio.Queue(maxsize=8)

    def cb(indata, frames, t, status):
        mono = indata.mean(axis=1).astype(np.float32)
        loop.call_soon_threadsafe(lambda: q.full() or q.put_nowait(mono))

    print(f"[music_sync] Listening to: {info['name']} @ {sr} Hz", flush=True)
    with sd.InputStream(device=device, channels=ch, samplerate=sr, blocksize=BLOCK, dtype="float32", callback=cb):
        while True:
            yield await q.get(), sr


# ---------------------------------------------------------------- main loop
async def run(args, blocks):
    analyzer = viz = None
    interval = 1.0 / args.fps
    last_send, last_rgb = 0.0, None
    async for ws in connect(args.url):          # reconnects automatically if the server restarts
        print(f"[music_sync] Connected to light server at {args.url}", flush=True)
        try:
            async for mono, sr in blocks:
                if analyzer is None:
                    analyzer = Analyzer(sr)
                    viz = Visualizer(args.style, args.palette, args.brightness, args.sensitivity, args.floor)
                rgb = viz.step(analyzer.feed(mono), len(mono) / sr)
                now = time.time()
                if now - last_send >= interval and (last_rgb is None or max(abs(a - b) for a, b in zip(rgb, last_rgb)) >= 2):
                    await ws.send(json.dumps({"r": rgb[0], "g": rgb[1], "b": rgb[2]}))
                    last_send, last_rgb = now, rgb
        except Exception as e:  # noqa: BLE001 - server went away: loop back and reconnect
            print(f"[music_sync] connection lost ({e}), retrying...", flush=True)
            await asyncio.sleep(2)


def main():
    p = argparse.ArgumentParser(description="Music-reactive colours for Ambient Light Sync")
    p.add_argument("--url", default="ws://localhost:8765", help="light server WebSocket (default %(default)s)")
    p.add_argument("--device", help="input device: index or name substring (default: auto-detect a monitor/loopback)")
    p.add_argument("--list-devices", action="store_true", help="list audio inputs and exit")
    p.add_argument("--style", choices=STYLES, default="spectrum")
    p.add_argument("--palette", choices=list(PALETTES), default="neon")
    p.add_argument("--brightness", type=float, default=1.0, help="0.0-1.0 (default 1.0)")
    p.add_argument("--sensitivity", type=float, default=1.0, help="0.2-3.0 (default 1.0)")
    p.add_argument("--floor", type=float, default=0.04, help="minimum glow in silence, 0-0.5 (default 0.04)")
    p.add_argument("--fps", type=int, default=30, help="max colour updates per second (default 30)")
    args = p.parse_args()
    if args.list_devices:
        return list_devices()
    args.brightness = min(1.0, max(0.0, args.brightness))
    try:
        asyncio.run(run(args, audio_blocks(pick_device(args.device))))
    except KeyboardInterrupt:
        print("\n[music_sync] stopped.", flush=True)


if __name__ == "__main__":
    main()
