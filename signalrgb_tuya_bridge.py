"""Local SignalRGB -> Tuya bridge.

Receives UDP packets: b"TY" + red + green + blue, then forwards the
latest colour to the configured Tuya device at a safe, throttled rate.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

import tinytuya

DEVICE_ID = os.environ.get("TUYA_DEVICE_ID", "bf892814e33b182ca5cbyl")
CONFIG_FILE = Path(os.environ.get("TUYA_CONFIG_FILE", str(Path.home() / "tinytuya.json")))
DEVICE_FILE = Path(os.environ.get("TUYA_DEVICE_FILE", str(Path(__file__).with_name("devices.json"))))
MODE_FILE = Path(os.environ.get("SIGNALRGB_MODE_FILE", str(Path(__file__).with_name("signalrgb_mode.json"))))
PACKET_LOG = Path(os.environ.get("SIGNALRGB_PACKET_LOG", str(Path(__file__).with_name("signalrgb_packets.log"))))
HOST = os.environ.get("SIGNALRGB_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SIGNALRGB_BRIDGE_PORT", "8766"))
UPDATE_SECONDS = float(os.environ.get("SIGNALRGB_TUYA_UPDATE_SECONDS", "0.1"))
LOCAL_ENABLED = os.environ.get("SIGNALRGB_TUYA_LOCAL", "1") != "0"

cloud = tinytuya.Cloud(configFile=str(CONFIG_FILE))
latest: tuple[int, int, int] | None = None
latest_lock = threading.Lock()
cloud_lock = threading.Lock()
packet_log_lock = threading.Lock()
local_device = None


def load_local_device():
    if not LOCAL_ENABLED or not DEVICE_FILE.exists():
        return None
    try:
        devices = json.loads(DEVICE_FILE.read_text(encoding="utf-8"))
        entry = next(item for item in devices if item.get("id") == DEVICE_ID)
        return tinytuya.Device(
            entry["id"], entry["ip"], entry["key"], version=float(entry.get("version", 3.5))
        )
    except (OSError, ValueError, KeyError, StopIteration, TypeError) as exc:
        print(f"Local Tuya setup unavailable: {exc}", flush=True)
        return None


def log_packet(rgb: tuple[int, int, int], address: tuple[str, int]) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} RGB={rgb} FROM={address[0]}:{address[1]}\n"
    try:
        with packet_log_lock:
            with PACKET_LOG.open("a", encoding="utf-8") as log_file:
                log_file.write(line)
    except OSError:
        pass


def rgb_to_hsv1000(rgb: tuple[int, int, int]) -> dict[str, int]:
    r, g, b = (value / 255 for value in rgb)
    high = max(r, g, b)
    low = min(r, g, b)
    delta = high - low
    hue = 0.0
    if delta:
        if high == r:
            hue = ((g - b) / delta) % 6
        elif high == g:
            hue = (b - r) / delta + 2
        else:
            hue = (r - g) / delta + 4
        hue *= 60
    saturation = 0 if high == 0 else delta / high
    return {
        "h": round(hue),
        "s": round(saturation * 1000),
        "v": round(high * 1000),
    }


def send_colour(rgb: tuple[int, int, int]) -> dict:
    colour = rgb_to_hsv1000(rgb)
    if local_device is not None:
        packed = f"{colour['h']:04x}{colour['s']:04x}{colour['v']:04x}"
        return local_device.set_multiple_values({"21": "colour", "24": packed})
    commands = [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data", "value": json.dumps(colour, separators=(",", ":"))},
    ]
    with cloud_lock:
        return cloud.cloudrequest(
            f"/v1.0/iot-03/devices/{DEVICE_ID}/commands",
            action="POST",
            post={"commands": commands},
        )


def signalrgb_mode_enabled() -> bool:
    try:
        data = json.loads(MODE_FILE.read_text(encoding="utf-8"))
        return bool(data.get("enabled", True))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return True


def sender() -> None:
    last_sent: tuple[int, int, int] | None = None
    while True:
        time.sleep(UPDATE_SECONDS)
        with latest_lock:
            rgb = latest
        if not signalrgb_mode_enabled():
            last_sent = None
            continue
        if rgb is None or rgb == last_sent:
            continue
        try:
            result = send_colour(rgb)
            print(f"SignalRGB {rgb} -> {result}", flush=True)
            last_sent = rgb
        except Exception as exc:
            print(f"Tuya error for {rgb}: {exc}", flush=True)


def main() -> None:
    global latest, local_device
    local_device = load_local_device()
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind((HOST, PORT))
    threading.Thread(target=sender, daemon=True).start()
    print(f"SignalRGB Tuya bridge listening on udp://{HOST}:{PORT}", flush=True)
    print(f"Device: {DEVICE_ID}; update interval: {UPDATE_SECONDS}s", flush=True)
    print(f"Transport: {'LAN' if local_device is not None else 'Cloud'}", flush=True)
    print(f"Mode file: {MODE_FILE}", flush=True)
    print(f"Packet log: {PACKET_LOG}", flush=True)
    while True:
        packet, address = receiver.recvfrom(1024)
        if len(packet) >= 5 and packet[:2] == b"TY":
            with latest_lock:
                latest = tuple(packet[2:5])  # type: ignore[assignment]
            log_packet(latest, address)
            print(f"RGB {latest} from {address[0]}:{address[1]}", flush=True)


if __name__ == "__main__":
    main()

