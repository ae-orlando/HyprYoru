#!/usr/bin/env python
"""Yoru Connections: explicit navigation shared by both radio menus.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import argparse
import shutil
import subprocess
import sys

from bluetooth import Bluetooth, input_device
from common import Cancelled, ConnectionError, GLib, Row, notify, operation_lock, panel, panel_visible, text
from ui import Menu
from wifi import Wifi


class Connections:
    def __init__(self, radio, origin=False, backend=None, ui=None):
        self.radio = radio
        self.origin = origin
        self.backend = backend if backend is not None else (Wifi() if radio == "wifi" else Bluetooth())
        self.ui = ui if ui is not None else Menu()
        self.view = "root"
        self.target = ""
        self.message = ""
        self.entries = {}

    def power(self, enabled):
        if self.radio == "bluetooth" and not enabled:
            devices = self.backend.connected_inputs()
            if devices and not self.ui.confirm("Turn Bluetooth off?", "This disconnects input devices: " + ", ".join(map(text, devices))):
                raise Cancelled()
        self.backend.set_power(enabled)

    def root(self):
        powered = self.backend.powered()
        rows = []
        self.entries = {}
        title = "Wi-Fi" if self.radio == "wifi" else "Bluetooth"
        if powered and self.radio == "wifi":
            entries = self.backend.networks()
            for entry in entries:
                status = "Connected" if entry["connected"] else "Saved" if entry["profile"] else "Open" if entry["security"] == "open" else "Secured"
                rows.append(Row(f"{entry['name']}  ·  {status}  ·  {entry['strength']}%", "details", entry["path"], active=entry["connected"], icon="network-wireless"))
                self.entries[entry["path"]] = entry
            connected = next((entry["name"] for entry in entries if entry["connected"]), None)
            status = "Connected to " + connected if connected else "On · choose a network · Refresh scans for changes"
            rows.append(Row("Refresh networks", "scan", icon="view-refresh"))
        elif powered:
            entries = self.backend.devices()
            for entry in entries:
                status = "Connected" if entry.get("Connected") else "Paired" if entry.get("Paired") else "Not paired"
                if entry["battery"] is not None:
                    status += f" · {entry['battery']}% battery"
                rows.append(Row(f"{entry['name']}  ·  {status}", "details", entry["path"], active=bool(entry.get("Connected")), icon=entry.get("Icon", "bluetooth")))
                self.entries[entry["path"]] = entry
            status = f"On · {sum(bool(entry.get('Connected')) for entry in entries)} connected · {self.backend.adapter()[1].get('Alias', 'Bluetooth')}"
            rows.append(Row("Find devices · 6-second scan", "scan", icon="edit-find"))
        else:
            status = title + " is off · saved connections are kept"
        rows.append(Row("Turn " + title + (" off" if powered else " on"), "power_off" if powered else "power_on", icon="system-shutdown"))
        rows.append(Row("Advanced settings", "advanced", icon="preferences-system"))
        rows.append(Row("Back to quick settings" if self.origin else "Close", "exit", icon="go-previous"))
        return title, status, rows

    def details(self):
        # Resolve the selected stable identifier against current system state.
        entries = self.backend.networks() if self.radio == "wifi" else self.backend.devices()
        entry = next((item for item in entries if item["path"] == self.target), None)
        if entry is None:
            self.view = "root"
            raise ConnectionError("That item is no longer available. Refresh the list.")
        self.entries[self.target] = entry
        rows = []
        if self.radio == "wifi":
            connected = entry["connected"]
            rows.append(Row("Disconnect" if connected else "Connect", "disconnect" if connected else "connect", self.target, icon="network-wireless"))
            if entry["profile"]:
                if entry["security"] in ["wpa-psk", "sae"]:
                    rows.append(Row("Update saved password", "password", self.target, icon="dialog-password"))
                rows.append(Row("Forget saved network…", "forget", self.target, urgent=True, icon="edit-delete"))
            status = f"{entry['strength']}% signal · {entry['security']} · " + ("Connected" if connected else "Saved" if entry["profile"] else "Not saved")
        else:
            if entry.get("Paired"):
                rows.append(Row("Disconnect" if entry.get("Connected") else "Connect", "disconnect" if entry.get("Connected") else "connect", self.target, icon=entry.get("Icon", "bluetooth")))
                rows.append(Row("Remove trust" if entry.get("Trusted") else "Trust this device…", "trust", self.target, icon="security-high"))
                rows.append(Row("Forget paired device…", "forget", self.target, urgent=True, icon="edit-delete"))
            else:
                rows.append(Row("Pair device…", "pair", self.target, icon="bluetooth"))
            status = ("Connected" if entry.get("Connected") else "Paired" if entry.get("Paired") else "Not paired") + " · " + entry["Address"]
            if entry["battery"] is not None:
                status += f" · {entry['battery']}% battery"
        rows.append(Row("Back", "back", icon="go-previous"))
        return "Network" if self.radio == "wifi" else "Device", entry["name"] + " · " + status, rows

    def advanced(self):
        if self.radio == "wifi":
            return "Wi-Fi settings", "Use the connection editor for enterprise, hidden networks, and saved profiles.", [Row("Open connection editor", "editor", icon="preferences-system-network"), Row("Back", "back", icon="go-previous")]
        _, info = self.backend.adapter()
        rows = [Row(("Stop" if info.get(option) else "Allow") + " " + label + ("" if info.get(option) else " · 2 minutes"), "adapter_option", option, active=bool(info.get(option)), icon="bluetooth") for option, label in [("Discoverable", "discoverability"), ("Pairable", "incoming pairing")]]
        rows.append(Row("Back", "back", icon="go-previous"))
        return "Bluetooth settings", "Nearby-device visibility is opt-in and time-limited.", rows

    def dispatch(self, row):
        if row.action == "exit":
            if self.origin:
                panel(True)
            return False
        if row.action == "back":
            self.view = "root"
            return True
        if row.action == "details":
            self.target = row.target
            self.view = "details"
            return True
        if row.action == "advanced":
            self.view = "advanced"
            return True
        if row.action == "editor":
            executable = shutil.which("nm-connection-editor")
            if not executable:
                raise ConnectionError("nm-connection-editor is not installed. Your existing profiles are unchanged.")
            subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return False
        with operation_lock(self.radio):
            self.perform(row)
        return True

    def perform(self, row):
        if row.action.startswith("power_"):
            self.power(row.action == "power_on")
            self.view = "root"
        elif row.action == "scan":
            self.ui.work("Refresh networks" if self.radio == "wifi" else "Find Bluetooth devices", self.backend.scan)
            self.view = "root"
        elif row.action == "adapter_option":
            enabled = not self.backend.adapter()[1].get(row.target)
            if not enabled or self.ui.confirm("Allow nearby devices?", "This enables " + row.target.lower() + " for two minutes."):
                self.backend.adapter_option(row.target, enabled)
        else:
            entry = self.entries[row.target]
            if row.action == "forget":
                if self.ui.confirm("Forget connection?", "Remove saved credentials for " + entry["name"] + "? This may also disconnect it."):
                    self.backend.forget(entry)
                    self.view = "root"
            elif row.action == "password":
                password = self.ui.password("Update Wi-Fi password", entry["name"])
                self.backend.password(entry, password)
                self.message = "Password updated. Choose Connect to retry."
            elif row.action == "connect":
                if self.radio == "wifi":
                    password = None
                    if not entry["profile"] and entry["security"] in ["wpa-psk", "sae"]:
                        password = self.ui.password("Wi-Fi password", entry["name"])
                    self.ui.work("Connect Wi-Fi", lambda cancel: self.backend.connect(entry, password, cancel))
                else:
                    self.ui.work("Connect Bluetooth", lambda cancel: self.backend.connect(entry, cancel))
            elif row.action == "disconnect":
                if self.radio == "bluetooth" and input_device(entry) and not self.ui.confirm("Disconnect input device?", "Disconnect " + entry["name"] + "? Make sure another keyboard or pointer is available."):
                    raise Cancelled()
                self.ui.work("Disconnect", lambda cancel: self.backend.disconnect(entry, cancel))
            elif row.action == "pair":
                self.backend.pair(entry, self.ui)
            elif row.action == "trust":
                trusted = not entry.get("Trusted")
                if not trusted or self.ui.confirm("Trust device?", "Allow " + entry["name"] + " to connect without asking again?"):
                    self.backend.trust(entry, trusted)

    def run(self):
        while True:
            try:
                title, status, rows = self.root() if self.view == "root" else self.details() if self.view == "details" else self.advanced()
                message = status + (" · " + self.message if self.message else "")
                self.message = ""
                key = self.view + (self.target if self.view == "details" else "")
                row = self.ui.choose(title, message, rows, key=key)
            except Cancelled:
                return
            except ConnectionError as error:
                try:
                    row = self.ui.choose("Connections unavailable", str(error), [Row("Retry", "back", icon="view-refresh"), Row("Back to quick settings" if self.origin else "Close", "exit", icon="go-previous")], key="error")
                except Cancelled:
                    return
            try:
                if not self.dispatch(row):
                    return
            except Cancelled:
                self.message = "Cancelled · no saved connections were removed."
            except (ConnectionError, GLib.Error) as error:
                self.message = str(error)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Yoru Connections — ae Orland · https://github.com/ae-orlando")
    parser.add_argument("radio", choices=["wifi", "bluetooth"])
    parser.add_argument("--from-swaync", action="store_true")
    parser.add_argument("--state", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--power", choices=["on", "off", "true", "false", "toggle"])
    args = parser.parse_args(argv)
    was_visible = args.from_swaync and panel_visible()
    panel_restored = False
    try:
        backend = Wifi() if args.radio == "wifi" else Bluetooth()
        if args.state:
            print("true" if backend.powered() else "false")
        elif args.status:
            if args.radio == "bluetooth":
                if backend.powered():
                    names = ", ".join(text(device["name"]) for device in backend.devices() if device.get("Connected"))
                    print("" + (" " + names if names else ""))
                else:
                    print("")
            else:
                print("" if backend.powered() else "󰖪")
        elif args.power:
            # The requested state is explicit: rapid clicks cannot blindly invert it.
            with operation_lock(args.radio):
                enabled = not backend.powered() if args.power == "toggle" else args.power in ["on", "true"]
                if args.radio == "bluetooth" and not enabled and backend.connected_inputs():
                    if was_visible:
                        panel(False)
                    try:
                        Connections(args.radio, backend=backend).power(enabled)
                    finally:
                        if was_visible:
                            panel(True)
                            panel_restored = True
                else:
                    backend.set_power(enabled)
        else:
            Connections(args.radio, args.from_swaync, backend=backend).run()
        return 0
    except (Cancelled, ConnectionError, GLib.Error, OSError) as error:
        if args.state:
            print("false")
        elif args.status:
            print("" if args.radio == "bluetooth" else "󰖪")
        else:
            if not isinstance(error, Cancelled):
                notify(str(error))
            # Stock SwayNC has no per-button rollback API. Refresh only on failure,
            # only while still visible, without rewriting config or restarting it.
            if args.power and was_visible and not panel_restored and panel_visible():
                panel(False)
                panel(True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
