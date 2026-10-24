"""NetworkManager-owned hotspot profiles, guarded transitions, and local sharing.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import io
import json
import os
import pwd
import re
import secrets
import subprocess
import uuid

from common import Cancelled, ConnectionError, GLib, call, props, wait_for
from wifi import PROFILE, ROOT, SERVICE, WIRELESS, variant_settings


def engaged(state):
    return bool(state.get("active") or state.get("phase") in ["starting", "stopping"])


def validate_settings(ssid, password, band, needs_password=False):
    if not 1 <= len(ssid.encode("utf-8")) <= 32 or any(ord(char) < 32 for char in ssid):
        raise ConnectionError("The hotspot name must be 1–32 UTF-8 bytes without control characters.")
    if band not in ["", "bg", "a"]:
        raise ConnectionError("Unsupported hotspot band.")
    if password:
        valid = 8 <= len(password.encode("utf-8")) <= 63 or bool(re.fullmatch(r"[0-9a-fA-F]{64}", password))
        if not valid:
            raise ConnectionError("Use an 8–63-byte password or a 64-digit hexadecimal key.")
    elif needs_password:
        raise ConnectionError("Enter or generate a password before saving a new hotspot.")


def generate_password():
    return secrets.token_urlsafe(18)


def qr_payload(ssid, password):
    def escape(value):
        return re.sub(r'([\\;,:\"])', r"\\\1", value)
    return f"WIFI:T:WPA;S:{escape(ssid)};P:{escape(password)};;"


def qr_png(ssid, password):
    try:
        import qrcode
    except ImportError as error:
        raise ConnectionError("QR sharing needs python-qrcode. Install it locally; no credentials are sent to a web service.") from error
    image = qrcode.make(qr_payload(ssid, password), box_size=8, border=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def parse_stations(output):
    stations = []
    for line in output.splitlines():
        match = re.match(r"Station ([0-9a-fA-F:]{17})\b", line)
        if match:
            stations.append({"mac": match[1].lower(), "signal": None, "rx": 0, "tx": 0, "seconds": 0})
        elif stations:
            for label, key in [("signal", "signal"), ("rx bytes", "rx"), ("tx bytes", "tx"), ("connected time", "seconds")]:
                match = re.match(r"\s*" + label + r":\s*(-?\d+)", line)
                if match:
                    stations[-1][key] = int(match[1])
    return stations


class Hotspot:
    def __init__(self, wifi):
        self.wifi = wifi
        self.bus = wifi.bus

    def snapshot(self):
        device, info = self.wifi.device()
        wireless = props(self.bus, SERVICE, device, WIRELESS)
        selected = None
        connection_state = 0
        active = info.get("ActiveConnection", "/")
        if active != "/":
            connection = props(self.bus, SERVICE, active, SERVICE + ".Connection.Active")
            connection_state = connection.get("State", 0)
            profile = connection.get("Connection", "/")
            if profile != "/":
                settings = call(self.bus, SERVICE, profile, PROFILE, "GetSettings").unpack()[0]
                if settings.get("802-11-wireless", {}).get("mode") == "ap":
                    selected = (profile, settings)
        running = selected is not None and wireless.get("Mode") == 3 and connection_state == 2
        phase = "active" if running else "starting" if selected and connection_state == 1 else "stopping" if selected and connection_state == 3 else "inactive"
        if selected is None:
            profiles = [(path, settings) for path, settings in self.wifi.profiles() if settings.get("802-11-wireless", {}).get("mode") == "ap" and (settings.get("connection", {}).get("interface-name") or info["Interface"]) == info["Interface"]]
            if profiles:
                selected = max(profiles, key=lambda item: item[1].get("connection", {}).get("timestamp", 0))
        path, settings = selected if selected else (None, {})
        wifi = settings.get("802-11-wireless", {})
        capabilities = wireless.get("WirelessCapabilities", 0)
        manager = self.wifi.properties()
        primary = manager.get("PrimaryConnection", "/")
        upstream = "No upstream connection"
        if primary != "/":
            kind = props(self.bus, SERVICE, primary, SERVICE + ".Connection.Active").get("Type", "")
            upstream = {"gsm": "Mobile broadband", "cdma": "Mobile broadband", "802-3-ethernet": "Ethernet", "802-11-wireless": "Wi-Fi"}.get(kind, "Network connection")
        raw_ssid = bytes(wifi.get("ssid", b"Yoru Hotspot"))
        hotspot_connection = phase in ["active", "starting", "stopping"]
        return {"device": device, "interface": info["Interface"], "profile": path, "uuid": settings.get("connection", {}).get("uuid"), "active": running, "phase": phase, "active_path": active if hotspot_connection else "/", "other_active": active if not hotspot_connection else "/", "supported": bool(capabilities & 0x40), "bands": [""] + (["bg"] if capabilities & 0x200 else []) + (["a"] if capabilities & 0x400 else []), "ssid": raw_ssid.decode("utf-8", "replace"), "raw_ssid": raw_ssid, "band": wifi.get("band", ""), "security": settings.get("802-11-wireless-security", {}).get("key-mgmt", "open" if path else "wpa-psk"), "shared": settings.get("ipv4", {}).get("method") == "shared", "upstream": upstream, "metered": manager.get("Metered") in [1, 3], "autoconnect": settings.get("connection", {}).get("autoconnect", False)}

    def clients(self, state):
        if not state["active"]:
            return []
        try:
            result = subprocess.run(["iw", "dev", state["interface"], "station", "dump"], capture_output=True, text=True, timeout=3)
            if result.returncode:
                return None
            clients = parse_stations(result.stdout)
            neighbours = subprocess.run(["ip", "-j", "neigh", "show", "dev", state["interface"]], capture_output=True, text=True, timeout=2)
            addresses = {entry.get("lladdr", "").lower(): entry.get("dst", "") for entry in json.loads(neighbours.stdout or "[]")} if neighbours.returncode == 0 else {}
            for client in clients:
                client["ip"] = addresses.get(client["mac"], "")
                client["name"] = "Connected device"
            return clients
        except (OSError, ValueError, subprocess.SubprocessError):
            return None

    def password(self, state):
        if not state["profile"]:
            raise ConnectionError("Save a protected hotspot before sharing its credentials.")
        secrets = call(self.bus, SERVICE, state["profile"], PROFILE, "GetSecrets", "(s)", ("802-11-wireless-security",)).unpack()[0]
        password = secrets.get("802-11-wireless-security", {}).get("psk")
        if not password:
            raise ConnectionError("The saved password is unavailable. Enter a new password explicitly; the current profile has not been changed.")
        return password

    def _settings(self, state, ssid, password, band, need_restore=False):
        if state["profile"] and state["security"] not in ["open", "wpa-psk", "sae"]:
            raise ConnectionError("This legacy hotspot security needs the network editor. Its saved credentials were left untouched.")
        protected = state["security"] in ["wpa-psk", "sae"]
        unchanged_name = bool(state["profile"] and ssid == state["ssid"])
        validate_settings("Existing hotspot" if unchanged_name else ssid, password, band, needs_password=not state["profile"] or not protected)
        if band not in state["bands"]:
            raise ConnectionError("This adapter does not support the selected hotspot band.")
        if state["profile"]:
            raw = call(self.bus, SERVICE, state["profile"], PROFILE, "GetSettings").get_child_value(0)
            settings = variant_settings(raw)
            if protected and (not password or need_restore):
                old_password = self.password(state)
                settings.setdefault("802-11-wireless-security", {})["psk"] = GLib.Variant("s", old_password)
            previous = {group: dict(values) for group, values in settings.items()}
        else:
            owner = pwd.getpwuid(os.getuid()).pw_name
            settings = {"connection": {"id": GLib.Variant("s", "Yoru Hotspot"), "uuid": GLib.Variant("s", str(uuid.uuid4())), "type": GLib.Variant("s", "802-11-wireless"), "permissions": GLib.Variant("as", [f"user:{owner}:"])}, "ipv6": {"method": GLib.Variant("s", "disabled")}}
            previous = None
        settings["connection"]["autoconnect"] = GLib.Variant("b", False)
        wireless = settings.setdefault("802-11-wireless", {})
        ssid_bytes = state["raw_ssid"] if unchanged_name else ssid.encode("utf-8")
        wireless.update({"ssid": GLib.Variant("ay", ssid_bytes), "mode": GLib.Variant("s", "ap")})
        if band != state["band"]:
            wireless.pop("channel", None)
        if band:
            wireless["band"] = GLib.Variant("s", band)
        else:
            wireless.pop("band", None)
        security = settings.setdefault("802-11-wireless-security", {})
        if not state["profile"] or not protected:
            security.update({"key-mgmt": GLib.Variant("s", "wpa-psk"), "proto": GLib.Variant("as", ["rsn"]), "pairwise": GLib.Variant("as", ["ccmp"]), "group": GLib.Variant("as", ["ccmp"])})
        if password:
            security["psk"] = GLib.Variant("s", password)
        if not state["profile"]:
            settings["ipv4"] = {"method": GLib.Variant("s", "shared")}
        return settings, previous

    def _checkpoint(self, state):
        try:
            # Leave room for system authentication while the old link remains
            # active. Shorten the deadline as soon as activation is authorized.
            return call(self.bus, SERVICE, ROOT, SERVICE, "CheckpointCreate", "(aouu)", ([state["device"]], 600, 0)).unpack()[0]
        except ConnectionError as error:
            if state["active"] or state["other_active"] != "/":
                raise ConnectionError("NetworkManager could not create a rollback checkpoint. The active connection was left untouched.") from error
            return None

    def _checkpoint_end(self, checkpoint, rollback=False):
        if not checkpoint:
            return
        if rollback:
            call(self.bus, SERVICE, ROOT, SERVICE, "CheckpointRollback", "(o)", (checkpoint,))
        try:
            call(self.bus, SERVICE, ROOT, SERVICE, "CheckpointDestroy", "(o)", (checkpoint,))
        except ConnectionError:
            if not rollback:
                raise

    def _activate(self, profile, state, cancel, checkpoint=None):
        if cancel.is_set():
            raise Cancelled()
        active = call(self.bus, SERVICE, ROOT, SERVICE, "ActivateConnection", "(ooo)", (profile, state["device"], "/")).unpack()[0]
        try:
            if checkpoint:
                call(self.bus, SERVICE, ROOT, SERVICE, "CheckpointAdjustRollbackTimeout", "(ou)", (checkpoint, 120))
            def ready():
                value = props(self.bus, SERVICE, active, SERVICE + ".Connection.Active").get("State")
                if value == 4:
                    raise ConnectionError("Hotspot activation failed. Check the adapter's band and regulatory restrictions.")
                return value == 2
            wait_for(ready, cancel, seconds=90)
        except (Cancelled, ConnectionError):
            try:
                call(self.bus, SERVICE, ROOT, SERVICE, "DeactivateConnection", "(o)", (active,))
            except ConnectionError:
                pass
            raise

    def save(self, ssid, password, band, cancel, restart_confirmed=False):
        state = self.snapshot()
        if state.get("phase") in ["starting", "stopping"]:
            raise ConnectionError("A hotspot transition is already in progress. Wait for it to settle before editing.")
        if not state["supported"]:
            raise ConnectionError("This Wi-Fi adapter does not support access-point mode.")
        if state["active"] and not restart_confirmed:
            raise ConnectionError("Changing an active hotspot requires an explicit restart confirmation.")
        settings, previous = self._settings(state, ssid, password, band, need_restore=state["active"])
        if cancel.is_set():
            raise Cancelled()
        checkpoint = self._checkpoint(state) if state["active"] else None
        profile = state["profile"]
        updated = False
        try:
            if profile:
                call(self.bus, SERVICE, profile, PROFILE, "Update", "(a{sa{sv}})", (settings,))
                updated = True
            else:
                profile = call(self.bus, SERVICE, ROOT + "/Settings", SERVICE + ".Settings", "AddConnection", "(a{sa{sv}})", (settings,)).unpack()[0]
            if state["active"]:
                if cancel.is_set():
                    raise Cancelled()
                call(self.bus, SERVICE, ROOT, SERVICE, "DeactivateConnection", "(o)", (state["active_path"],))
                self._activate(profile, state, cancel, checkpoint)
            self._checkpoint_end(checkpoint)
        except (Cancelled, ConnectionError) as original:
            recovery_errors = []
            if updated and previous is not None:
                try:
                    call(self.bus, SERVICE, profile, PROFILE, "Update", "(a{sa{sv}})", (previous,))
                except ConnectionError as error:
                    recovery_errors.append(error)
            try:
                self._checkpoint_end(checkpoint, rollback=True)
            except ConnectionError as error:
                recovery_errors.append(error)
            if recovery_errors:
                raise ConnectionError("The update failed and automatic recovery reported an error. Check the active hotspot and saved profile before retrying; no profile was deleted.") from original
            raise

    def start(self, cancel, switch_confirmed=False):
        if cancel.is_set():
            raise Cancelled()
        state = self.snapshot()
        if state.get("phase") in ["starting", "stopping"]:
            raise ConnectionError("A hotspot transition is already in progress.")
        if state["active"]:
            return
        if not state["supported"] or not state["profile"]:
            raise ConnectionError("Save a protected hotspot profile before starting it.")
        if state["security"] not in ["wpa-psk", "sae"]:
            raise ConnectionError("Set a strong password before starting this hotspot.")
        if state["other_active"] != "/" and not switch_confirmed:
            raise ConnectionError("Starting the hotspot requires confirmation before replacing the current Wi-Fi connection.")
        checkpoint = self._checkpoint(state)
        try:
            self.wifi.set_power(True)
            self._activate(state["profile"], state, cancel, checkpoint)
            self._checkpoint_end(checkpoint)
        except (Cancelled, ConnectionError):
            self._checkpoint_end(checkpoint, rollback=True)
            raise

    def stop(self, cancel, confirmed=False):
        state = self.snapshot()
        if not state["active"]:
            return
        if not confirmed:
            raise ConnectionError("Stopping a hotspot requires confirmation because connected clients will be disconnected.")
        if cancel.is_set():
            raise Cancelled()
        call(self.bus, SERVICE, ROOT, SERVICE, "DeactivateConnection", "(o)", (state["active_path"],))
        wait_for(lambda: not self.snapshot()["active"], cancel, seconds=10)
