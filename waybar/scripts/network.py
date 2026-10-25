#!/usr/bin/env python3
"""Compact, read-only NetworkManager status for Waybar, including hotspot mode.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from html import escape
import json
from pathlib import Path
import sys

# Reuse the drawer's passive D-Bus helpers; never scan or read saved secrets.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rofi/launchers/connectivity"))
from common import ConnectionError, Gio, GLib, props
from wifi import AP, DEVICE, ROOT, SERVICE, WIRELESS

ACTIVE = SERVICE + ".Connection.Active"
ICONS = {"hotspot": "󰀂", "wifi": "", "ethernet": "󰈀", "mobile": "󰢟", "network": "󰛳",
         "off": "󰖪", "idle": "", "disconnected": "󰌙", "unavailable": "󰌙"}


def literal(value):
    value = "".join(char if char.isprintable() else " " for char in str(value))
    return escape(value[:80] + ("…" if len(value) > 80 else ""), quote=False)


def result(kind, tooltip, connected=False, connecting=False):
    classes = [kind]
    if connected:
        classes.append("connected")
    if connecting:
        classes.append("connecting")
    return {"text": ICONS[kind], "alt": kind, "class": classes, "tooltip": tooltip}


def snapshot(read):
    """read(path, interface) is only GetAll; injectable for isolated tests."""
    manager = read(ROOT, SERVICE)
    if not manager.get("NetworkingEnabled", True):
        return result("off", "Networking disabled")
    devices = []
    for path in manager.get("Devices", []):
        try:
            device = read(path, DEVICE)
            wireless = read(path, WIRELESS) if device.get("DeviceType") == 2 else {}
            devices.append((path, device, wireless))
        except ConnectionError:
            continue  # Hot-plugged devices can disappear between property reads.
    primary = manager.get("PrimaryConnection", "/")

    # Sharing takes priority over an uplink icon, not over the actual uplink.
    # Wireless.Mode=AP is sufficient: do not enumerate saved profiles/GetSettings.
    for _path, device, wireless in devices:
        if wireless.get("Mode") == 3 and device.get("State") == 100:
            upstream = "No upstream connection"
            if primary != "/" and primary != device.get("ActiveConnection", "/"):
                try:
                    kind = read(primary, ACTIVE).get("Type", "")
                    upstream = {"802-3-ethernet": "Ethernet uplink", "802-11-wireless": "Wi-Fi uplink",
                                "gsm": "Mobile broadband uplink", "cdma": "Mobile broadband uplink"}.get(kind, "Network uplink")
                except ConnectionError:
                    pass
            return result("hotspot", "Hotspot active\nSharing on " + literal(device.get("Interface", "Wi-Fi")) + "\n" + upstream, connected=True)

    # Prefer the default route's physical adapter; VPN/virtual adapters must not
    # hide a functioning Wi-Fi/Ethernet link when they own the primary route.
    active = [entry for entry in devices if entry[1].get("State") == 100
              and entry[1].get("DeviceType") != 32 and entry[1].get("Interface") != "lo"]
    physical = [entry for entry in active if entry[1].get("DeviceType") in (1, 2, 8)]
    candidates = physical or [entry for entry in active if primary != "/"
                              and entry[1].get("ActiveConnection") == primary]
    if candidates:
        _path, device, wireless = max(candidates, key=lambda entry: entry[1].get("ActiveConnection") == primary)
        interface = literal(device.get("Interface", "Network"))
        kind = device.get("DeviceType")
        if kind == 2:
            details = "Wi-Fi connected\n" + interface
            point = wireless.get("ActiveAccessPoint", "/")
            if point != "/":
                try:
                    access_point = read(point, AP)
                    ssid = bytes(access_point.get("Ssid", [])).decode("utf-8", errors="replace")
                    strength = max(0, min(100, int(access_point.get("Strength", 0))))
                    details = "Wi-Fi · " + literal(ssid) + f"\nSignal {strength}% · " + interface
                except (ConnectionError, TypeError, ValueError):
                    pass
            return result("wifi", details, connected=True)
        if kind == 1:
            return result("ethernet", "Ethernet connected\n" + interface, connected=True)
        if kind == 8:
            return result("mobile", "Mobile broadband connected\n" + interface, connected=True)
        return result("network", "Network connected\n" + interface, connected=True)

    wifi = [entry for entry in devices if entry[1].get("DeviceType") == 2]
    if wifi:
        if not manager.get("WirelessHardwareEnabled", True):
            return result("off", "Wi-Fi hardware blocked")
        if not manager.get("WirelessEnabled", False):
            return result("off", "Wi-Fi off")
        for _path, device, wireless in wifi:
            if 40 <= device.get("State", 0) <= 90:
                if wireless.get("Mode") == 3:
                    return result("hotspot", "Hotspot starting", connecting=True)
                return result("wifi", "Wi-Fi connecting", connecting=True)
        return result("idle", "Wi-Fi on · Not connected")
    return result("disconnected", "No network connection")


def main():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        status = snapshot(lambda path, interface: props(bus, SERVICE, path, interface))
    except (ConnectionError, GLib.Error):
        status = result("unavailable", "NetworkManager unavailable")
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
