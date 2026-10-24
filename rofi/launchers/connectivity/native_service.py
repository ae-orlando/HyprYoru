"""UI-independent native drawer state, guarded operations, and simulation.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import copy

from bluetooth import Bluetooth, input_device
from common import Cancelled, ConnectionError, Gio, GLib, interactive_authorization, operation_lock
from hotspot import Hotspot, engaged
from wifi import Wifi


def stable_entries(entries, old_order, kind):
    """Keep live RSSI changes from moving a row under the pointer."""
    order = {identity: index for index, identity in enumerate(old_order)}
    def key(item):
        identity = item.get("path", item.get("mac"))
        group = (not item["connected"], not bool(item["profile"])) if kind == "networks" else (not item.get("Connected", False), not item.get("Paired", False)) if kind == "devices" else ()
        return group, order.get(identity, len(order))
    return sorted(entries, key=key)


class NativeService:
    def __init__(self):
        self.wifi = None
        self.bluetooth = None
        self.hotspot = None
        self._subscriptions = []

    def ensure(self):
        if self.wifi is None:
            self.wifi = Wifi()
            self.bluetooth = Bluetooth(bus=self.wifi.bus)
            self.hotspot = Hotspot(self.wifi)

    def read(self):
        self.ensure()
        result = {"wifi_on": False, "bluetooth_on": False, "wifi_error": "", "bluetooth_error": "", "networks": [], "devices": [], "hotspot": None, "clients": None}
        try:
            result["wifi_on"] = self.wifi.powered()
            result["hotspot"] = self.hotspot.snapshot()
            if result["hotspot"]["active"]:
                result["clients"] = self.hotspot.clients(result["hotspot"])
            elif result["wifi_on"] and result["hotspot"].get("phase", "inactive") == "inactive":
                result["networks"] = self.wifi.networks()
        except (ConnectionError, GLib.Error) as error:
            result["wifi_error"] = str(error)
        try:
            result["bluetooth_on"] = self.bluetooth.powered()
            if result["bluetooth_on"]:
                result["devices"] = self.bluetooth.devices()
        except (ConnectionError, GLib.Error) as error:
            result["bluetooth_error"] = str(error)
        return result

    def watch(self, changed):
        if self._subscriptions or self.wifi is None:
            return
        signals = [
            ("org.freedesktop.NetworkManager", "org.freedesktop.DBus.Properties", "PropertiesChanged"),
            ("org.freedesktop.NetworkManager", "org.freedesktop.NetworkManager", "DeviceAdded"),
            ("org.freedesktop.NetworkManager", "org.freedesktop.NetworkManager", "DeviceRemoved"),
            ("org.freedesktop.NetworkManager", "org.freedesktop.NetworkManager.Settings.Connection", "Updated"),
            ("org.bluez", "org.freedesktop.DBus.Properties", "PropertiesChanged"),
            ("org.bluez", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"),
            ("org.bluez", "org.freedesktop.DBus.ObjectManager", "InterfacesRemoved"),
        ]
        for service, interface, signal in signals:
            identifier = self.wifi.bus.signal_subscribe(service, interface, signal, None, None, Gio.DBusSignalFlags.NONE, lambda *_args: changed())
            self._subscriptions.append(identifier)
        for name in ["org.freedesktop.NetworkManager", "org.bluez"]:
            identifier = self.wifi.bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged", "/org/freedesktop/DBus", name, Gio.DBusSignalFlags.NONE, lambda *_args: changed())
            self._subscriptions.append(identifier)

    def close(self):
        if self.wifi:
            for identifier in self._subscriptions:
                self.wifi.bus.signal_unsubscribe(identifier)
        self._subscriptions.clear()

    def _confirm(self, prompts, title, message):
        if not prompts.confirm(title, message):
            raise Cancelled()

    def _sharing_warning(self, state):
        clients = self.hotspot.clients(state)
        count = "connected devices" if clients is None else f"{len(clients)} connected device(s)"
        return f"This stops the hotspot and disconnects {count}. Saved credentials will be kept."

    def perform(self, action, values, prompts, cancel):
        self.ensure()
        radio = "bluetooth" if action.startswith("bt_") else "wifi"
        with operation_lock(radio), interactive_authorization():
            if cancel.is_set():
                raise Cancelled()
            if action == "wifi_power":
                state = self.hotspot.snapshot()
                if not values["enabled"] and engaged(state):
                    self._confirm(prompts, "Turn Wi-Fi off?", self._sharing_warning(state))
                self.wifi.set_power(values["enabled"])
            elif action == "wifi_scan":
                if engaged(self.hotspot.snapshot()):
                    raise ConnectionError("The hotspot is using this adapter. Stop sharing before scanning for another Wi-Fi network.")
                self.wifi.scan(cancel)
            elif action in ["wifi_connect", "wifi_disconnect", "wifi_forget", "wifi_password"]:
                state = self.hotspot.snapshot()
                if engaged(state):
                    raise ConnectionError("Hotspot mode is active. Stop sharing explicitly before changing Wi-Fi connections.")
                network = next((entry for entry in self.wifi.networks() if entry["path"] == values["path"]), None)
                if network is None:
                    raise ConnectionError("That network is no longer available. Refresh the list.")
                if action == "wifi_connect":
                    password = None
                    if not network["profile"] and network["security"] in ["wpa-psk", "sae"]:
                        password = prompts.password("Join network", network["name"])
                    elif not network["profile"] and network["security"] == "open":
                        self._confirm(prompts, "Join an open network?", network["name"] + " does not encrypt the Wi-Fi link. Only join networks you trust.")
                    self.wifi.connect(network, password, cancel)
                elif action == "wifi_disconnect":
                    self.wifi.disconnect(network, cancel)
                elif action == "wifi_forget":
                    self._confirm(prompts, "Forget network?", "Remove saved credentials for " + network["name"] + "? This may disconnect it.")
                    self.wifi.forget(network)
                else:
                    password = prompts.password("Update password", network["name"])
                    self.wifi.password(network, password)
            elif action.startswith("hotspot_"):
                state = self.hotspot.snapshot()
                if action == "hotspot_stop":
                    self._confirm(prompts, "Stop sharing?", self._sharing_warning(state))
                    self.hotspot.stop(cancel, confirmed=True)
                elif action == "hotspot_start":
                    if not state["profile"]:
                        raise ConnectionError("Save a name and password below before starting your hotspot.")
                    if state["other_active"] != "/":
                        self._confirm(prompts, "Switch to hotspot mode?", "The current Wi-Fi connection will be disconnected. Ethernet or mobile broadband can still provide internet.")
                    self.hotspot.start(cancel, switch_confirmed=True)
                elif action == "hotspot_save":
                    if values.get("profile", state["profile"]) != state["profile"]:
                        raise ConnectionError("The hotspot profile changed while editing. Reload the saved settings before applying changes.")
                    expected = values.get("expected")
                    if expected and any(state[key] != expected[key] for key in ["ssid", "band"]):
                        raise ConnectionError("The saved hotspot settings changed externally. Reset the form before applying your edits.")
                    if state["active"]:
                        self._confirm(prompts, "Apply and restart hotspot?", self._sharing_warning(state))
                    self.hotspot.save(values["ssid"], values["password"] or None, values["band"], cancel, restart_confirmed=state["active"])
            elif action == "bt_power":
                names = self.bluetooth.connected_inputs() if not values["enabled"] else []
                if names:
                    self._confirm(prompts, "Disconnect input devices?", "Turning Bluetooth off disconnects: " + ", ".join(names))
                self.bluetooth.set_power(values["enabled"])
            elif action == "bt_scan":
                self.bluetooth.scan(cancel)
            elif action == "bt_option":
                if values["enabled"]:
                    self._confirm(prompts, "Allow nearby devices?", "This enables " + values["option"].lower() + " for two minutes.")
                self.bluetooth.adapter_option(values["option"], values["enabled"])
            else:
                device = next((entry for entry in self.bluetooth.devices() if entry["path"] == values["path"]), None)
                if device is None:
                    raise ConnectionError("That device is no longer available.")
                if action == "bt_connect":
                    self.bluetooth.connect(device, cancel)
                elif action == "bt_disconnect":
                    if input_device(device):
                        self._confirm(prompts, "Disconnect input device?", "Make sure another keyboard or pointer is available before disconnecting " + device["name"] + ".")
                    self.bluetooth.disconnect(device, cancel)
                elif action == "bt_pair":
                    self.bluetooth.pair(device, prompts, cancel)
                elif action == "bt_forget":
                    self._confirm(prompts, "Forget paired device?", "Remove pairing credentials for " + device["name"] + "?")
                    self.bluetooth.forget(device)
                elif action == "bt_trust":
                    if values["enabled"]:
                        self._confirm(prompts, "Trust this device?", "Allow " + device["name"] + " to connect without asking again?")
                    self.bluetooth.trust(device, values["enabled"])

    def share(self):
        self.ensure()
        with interactive_authorization():
            state = self.hotspot.snapshot()
            # Secrets are retrieved only for an explicit Share/Show action.
            state["ssid"] = state["raw_ssid"].decode("utf-8")
            return state["ssid"], self.hotspot.password(state)


class DemoService:
    """Interactive visual previews that cannot reach any real network backend."""
    def __init__(self):
        self.data = {"wifi_on": True, "bluetooth_on": True, "wifi_error": "", "bluetooth_error": "", "networks": [{"path": "/demo/ap/1", "name": "Night garden", "ssid": b"Night garden", "security": "wpa-psk", "strength": 92, "profile": "/demo/saved/1", "connected": False}, {"path": "/demo/ap/2", "name": "Studio network", "ssid": b"Studio network", "security": "sae", "strength": 73, "profile": None, "connected": False}], "devices": [{"path": "/demo/device/1", "name": "Studio headphones", "Address": "02:00:00:00:00:01", "Connected": True, "Paired": True, "Trusted": True, "battery": 82, "Icon": "audio-headphones-symbolic"}, {"path": "/demo/device/2", "name": "Wireless keyboard", "Address": "02:00:00:00:00:02", "Connected": False, "Paired": True, "Trusted": True, "battery": 67, "Icon": "input-keyboard-symbolic"}], "hotspot": {"active": True, "supported": True, "profile": "/demo/hotspot", "uuid": "demo", "ssid": "Yoru guest", "raw_ssid": b"Yoru guest", "band": "bg", "bands": ["", "bg", "a"], "security": "wpa-psk", "shared": True, "upstream": "Mobile broadband", "metered": True, "autoconnect": False, "other_active": "/"}, "clients": [{"name": "Pixel phone", "mac": "02:00:00:10:00:01", "ip": "10.42.0.18", "signal": -41, "rx": 58000000, "tx": 124000000, "seconds": 460}, {"name": "Tablet", "mac": "02:00:00:10:00:02", "ip": "10.42.0.29", "signal": -53, "rx": 14000000, "tx": 45000000, "seconds": 320}, {"name": "Guest laptop", "mac": "02:00:00:10:00:03", "ip": "10.42.0.46", "signal": -62, "rx": 9000000, "tx": 27000000, "seconds": 140}]}

    def read(self):
        data = copy.deepcopy(self.data)
        if data["hotspot"]["active"] or not data["wifi_on"]:
            data["networks"] = []
        if not data["hotspot"]["active"]:
            data["clients"] = []
        if not data["bluetooth_on"]:
            data["devices"] = []
        return data

    def watch(self, changed):
        pass

    def close(self):
        pass

    def perform(self, action, values, prompts, cancel):
        if cancel.wait(0.25):
            raise Cancelled()
        if action in ["wifi_power", "bt_power"]:
            self.data["wifi_on" if action == "wifi_power" else "bluetooth_on"] = values["enabled"]
            if action == "wifi_power" and not values["enabled"]:
                self.data["hotspot"]["active"] = False
        elif action in ["hotspot_stop", "hotspot_start", "hotspot_save"]:
            if action in ["hotspot_stop", "hotspot_save"] and not prompts.confirm("Simulation only", "This would restart or stop a real hotspot. No real radios are attached to this preview."):
                raise Cancelled()
            self.data["hotspot"]["active"] = action != "hotspot_stop"
            if action == "hotspot_save":
                self.data["hotspot"].update({"ssid": values["ssid"], "band": values["band"]})

    def share(self):
        return "Yoru guest", "YoruPreviewOnly2026"
