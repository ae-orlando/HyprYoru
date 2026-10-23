"""NetworkManager backend: stable AP paths, saved UUIDs, and private secrets.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import uuid

from common import Cancelled, ConnectionError, Gio, GLib, call, props, set_prop, wait_for

SERVICE = "org.freedesktop.NetworkManager"
ROOT = "/org/freedesktop/NetworkManager"
DEVICE = SERVICE + ".Device"
WIRELESS = DEVICE + ".Wireless"
AP = SERVICE + ".AccessPoint"
PROFILE = SERVICE + ".Settings.Connection"


def security(properties):
    # NM80211ApSecurityFlags (libnm): PSK=0x100, 802.1X=0x200, SAE=0x400.
    flags = properties.get("RsnFlags", 0) | properties.get("WpaFlags", 0)
    if flags & (0x200 | 0x2000):
        return "enterprise"
    if flags & 0x100:
        return "wpa-psk"
    if flags & 0x400:
        return "sae"
    if flags & (0x800 | 0x1000):
        return "owe"
    return "wep" if properties.get("Flags", 0) & 1 else "open"


def variant_settings(value):
    """Preserve property signatures when explicitly updating a saved password."""
    result = {}
    for index in range(value.n_children()):
        group = value.get_child_value(index)
        properties = group.get_child_value(1)
        result[group.get_child_value(0).get_string()] = {
            properties.get_child_value(i).get_child_value(0).get_string(): properties.get_child_value(i).get_child_value(1).get_variant()
            for i in range(properties.n_children())
        }
    return result


class Wifi:
    def __init__(self, bus=None):
        self.bus = bus if bus is not None else Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def properties(self):
        return props(self.bus, SERVICE, ROOT, SERVICE)

    def powered(self):
        self.device()
        info = self.properties()
        return bool(info.get("WirelessEnabled") and info.get("WirelessHardwareEnabled"))

    def set_power(self, enabled):
        self.device()
        if enabled and not self.properties().get("WirelessHardwareEnabled"):
            raise ConnectionError("Wi-Fi is hardware-blocked. Check the laptop's wireless switch or airplane key.")
        set_prop(self.bus, SERVICE, ROOT, SERVICE, "WirelessEnabled", "b", enabled)
        wait_for(lambda: self.powered() == enabled, seconds=5)

    def device(self):
        devices = []
        for path in call(self.bus, SERVICE, ROOT, SERVICE, "GetDevices").unpack()[0]:
            properties = props(self.bus, SERVICE, path, DEVICE)
            if properties.get("DeviceType") == 2:
                devices.append((properties.get("State") == 100, path, properties))
        if not devices:
            raise ConnectionError("No Wi-Fi adapter is available.")
        _, path, properties = max(devices, key=lambda item: item[0])
        return path, properties

    def profiles(self):
        result = []
        paths = call(self.bus, SERVICE, ROOT + "/Settings", SERVICE + ".Settings", "ListConnections").unpack()[0]
        for path in paths:
            try:
                settings = call(self.bus, SERVICE, path, PROFILE, "GetSettings").unpack()[0]
                if settings.get("connection", {}).get("type") == "802-11-wireless":
                    result.append((path, settings))
            except ConnectionError:
                continue  # Some profiles may be owned by another user.
        return result

    def networks(self):
        device, info = self.device()
        wireless = props(self.bus, SERVICE, device, WIRELESS)
        active = wireless.get("ActiveAccessPoint", "/")
        profiles = self.profiles()
        result = {}
        for path in call(self.bus, SERVICE, device, WIRELESS, "GetAccessPoints").unpack()[0]:
            properties = props(self.bus, SERVICE, path, AP)
            ssid = bytes(properties.get("Ssid", []))
            if not ssid:
                continue
            kind = security(properties)
            saved = []
            for profile, settings in profiles:
                connection = settings["connection"]
                configured = settings.get("802-11-wireless-security", {}).get("key-mgmt", "open")
                configured = "enterprise" if configured in ["wpa-eap", "ieee8021x", "wpa-eap-suite-b-192"] else "wep" if configured == "none" else configured
                compatible = configured == kind or (configured == "sae" and properties.get("RsnFlags", 0) & 0x400)
                available = info.get("AvailableConnections")
                if bytes(settings.get("802-11-wireless", {}).get("ssid", [])) == ssid and compatible and (connection.get("interface-name") or info["Interface"]) == info["Interface"] and (available is None or profile in available):
                    saved.append((profile, connection["uuid"]))
            entry = {"path": path, "device": device, "ssid": ssid, "name": ssid.decode("utf-8", "replace"), "security": kind, "strength": properties.get("Strength", 0), "connected": path == active, "profile": saved[0][0] if saved else None, "uuid": saved[0][1] if saved else None}
            key = (ssid, kind)
            old = result.get(key)
            if old is None or (entry["connected"], entry["strength"]) > (old["connected"], old["strength"]):
                result[key] = entry
        return sorted(result.values(), key=lambda item: (not item["connected"], not bool(item["profile"]), -item["strength"], item["name"]))

    def scan(self, cancel):
        if cancel.is_set():
            raise Cancelled()
        device, _ = self.device()
        before = props(self.bus, SERVICE, device, WIRELESS).get("LastScan", -1)
        call(self.bus, SERVICE, device, WIRELESS, "RequestScan", "(a{sv})", ({},))
        wait_for(lambda: props(self.bus, SERVICE, device, WIRELESS).get("LastScan", -1) > before, cancel, seconds=10)

    def connect(self, network, password, cancel):
        if cancel.is_set():
            raise Cancelled()
        if network["profile"]:
            active = call(self.bus, SERVICE, ROOT, SERVICE, "ActivateConnection", "(ooo)", (network["profile"], network["device"], network["path"])).unpack()[0]
        else:
            kind = network["security"]
            if kind in ["enterprise", "wep"]:
                raise ConnectionError("This network needs an advanced profile. Use Advanced settings to configure it.")
            settings = {
                "connection": {"id": GLib.Variant("s", network["name"]), "uuid": GLib.Variant("s", str(uuid.uuid4())), "type": GLib.Variant("s", "802-11-wireless")},
                "802-11-wireless": {"ssid": GLib.Variant("ay", network["ssid"]), "mode": GLib.Variant("s", "infrastructure")},
                "ipv4": {"method": GLib.Variant("s", "auto")},
                "ipv6": {"method": GLib.Variant("s", "auto")},
            }
            if kind != "open":
                settings["802-11-wireless-security"] = {"key-mgmt": GLib.Variant("s", kind)}
                if kind in ["wpa-psk", "sae"]:
                    if not password:
                        raise Cancelled()
                    settings["802-11-wireless-security"]["psk"] = GLib.Variant("s", password)
            active = call(self.bus, SERVICE, ROOT, SERVICE, "AddAndActivateConnection", "(a{sa{sv}}oo)", (settings, network["device"], network["path"])).unpack()[1]
        try:
            def connected():
                state = props(self.bus, SERVICE, active, SERVICE + ".Connection.Active").get("State")
                if state == 4:
                    raise ConnectionError("Connection failed. The saved profile was kept; check the password or try again.")
                return state == 2
            wait_for(connected, cancel, seconds=35)
        except (Cancelled, ConnectionError):
            try:
                call(self.bus, SERVICE, ROOT, SERVICE, "DeactivateConnection", "(o)", (active,))
            except ConnectionError:
                pass  # NetworkManager may already have removed the failed activation.
            raise

    def disconnect(self, network, cancel):
        if not cancel.is_set():
            call(self.bus, SERVICE, network["device"], DEVICE, "Disconnect")

    def forget(self, network):
        if network["profile"]:
            call(self.bus, SERVICE, network["profile"], PROFILE, "Delete")

    def password(self, network, password):
        if network["security"] not in ["wpa-psk", "sae"]:
            raise ConnectionError("Use Advanced settings for this security type.")
        raw = call(self.bus, SERVICE, network["profile"], PROFILE, "GetSettings").get_child_value(0)
        settings = variant_settings(raw)
        settings.setdefault("802-11-wireless-security", {})["psk"] = GLib.Variant("s", password)
        call(self.bus, SERVICE, network["profile"], PROFILE, "Update", "(a{sa{sv}})", (settings,))
