"""BlueZ backend with scoped discovery and an explicit pairing agent.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from pathlib import Path
import subprocess

from common import Cancelled, ConnectionError, Gio, GLib, authorization_flags, call, close_notice, notify, private_context, props, set_prop, wait_for

SERVICE = "org.bluez"
ADAPTER = SERVICE + ".Adapter1"
DEVICE = SERVICE + ".Device1"
AGENT = "/org/yoru/Connections/Agent"
AGENT_XML = """<node><interface name="org.bluez.Agent1">
<method name="Release"/>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="Cancel"/>
</interface></node>"""


def input_device(device):
    uuids = [value.lower() for value in device.get("UUIDs", [])]
    return device.get("Icon", "").startswith(("input-", "keyboard", "mouse")) or any(value.startswith(("00001124-", "00001812-")) for value in uuids)


class Bluetooth:
    def __init__(self, bus=None):
        self.bus = bus if bus is not None else Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self._pair_cancelled = False

    def objects(self):
        return call(self.bus, SERVICE, "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects").unpack()[0]

    def adapter(self):
        adapters = [(path, interfaces[ADAPTER]) for path, interfaces in self.objects().items() if ADAPTER in interfaces]
        if not adapters:
            raise ConnectionError("No Bluetooth adapter is available. Check that Bluetooth is enabled in firmware.")
        return sorted(adapters)[0]

    def powered(self):
        return bool(self.adapter()[1].get("Powered"))

    def devices(self):
        adapter, _ = self.adapter()
        result = []
        for path, interfaces in self.objects().items():
            device = interfaces.get(DEVICE)
            if device is None or device.get("Adapter") != adapter:
                continue
            result.append({**device, "path": path, "name": device.get("Alias") or device.get("Name") or device["Address"], "battery": interfaces.get(SERVICE + ".Battery1", {}).get("Percentage")})
        return sorted(result, key=lambda item: (not item.get("Connected", False), not item.get("Paired", False), item["name"].casefold()))

    def connected_inputs(self):
        return [device["name"] for device in self.devices() if device.get("Connected") and input_device(device)]

    def set_power(self, enabled):
        path, _ = self.adapter()
        if enabled:
            # Only unblock this controller, never other radios or other adapters.
            for entry in Path("/sys/class/rfkill").glob("rfkill*"):
                try:
                    if (entry / "type").read_text().strip() != "bluetooth" or (entry / "name").read_text().strip() != path.rsplit("/", 1)[-1]:
                        continue
                    if (entry / "hard").read_text().strip() == "1":
                        raise ConnectionError("Bluetooth is hardware-blocked. Check the wireless switch or airplane key.")
                    if (entry / "soft").read_text().strip() == "1":
                        subprocess.run(["rfkill", "unblock", entry.name.removeprefix("rfkill")], capture_output=True, check=True, timeout=3)
                except OSError as error:
                    raise ConnectionError("Could not access Bluetooth's radio block state.") from error
                except subprocess.SubprocessError as error:
                    raise ConnectionError("Bluetooth could not be unblocked. Check radio-control permissions.") from error
        set_prop(self.bus, SERVICE, path, ADAPTER, "Powered", "b", enabled)
        wait_for(lambda: self.powered() == enabled, seconds=5)

    def scan(self, cancel):
        if cancel.is_set():
            raise Cancelled()
        path, _ = self.adapter()
        owned = False
        try:
            call(self.bus, SERVICE, path, ADAPTER, "StartDiscovery")
            owned = True
            if cancel.wait(6):
                raise Cancelled()
        finally:
            if owned:
                call(self.bus, SERVICE, path, ADAPTER, "StopDiscovery")

    def _await(self, path, method, cancel=None):
        if GLib.MainContext.get_thread_default() is None:
            with private_context():
                return self._await(path, method, cancel)
        context = GLib.MainContext.get_thread_default()
        loop = GLib.MainLoop.new(context, False)
        outcome = []

        def complete(connection, result, *_user_data):
            try:
                connection.call_finish(result)
                outcome.append(None)
            except GLib.Error as error:
                outcome.append(ConnectionError(error.message))
            loop.quit()

        self.bus.call(SERVICE, path, DEVICE, method, None, None, authorization_flags(), 35000, None, complete)
        watcher = None
        if cancel is not None:
            def check_cancel():
                if not cancel.is_set():
                    return True
                try:
                    call(self.bus, SERVICE, path, DEVICE, "CancelPairing" if method == "Pair" else "Disconnect")
                except ConnectionError:
                    pass
                return False
            watcher = GLib.timeout_source_new(100)
            watcher.set_callback(lambda *_args: check_cancel())
            watcher.attach(context)
        try:
            loop.run()
            if self._pair_cancelled or (cancel is not None and cancel.is_set()):
                raise Cancelled()
            if outcome[0]:
                raise outcome[0]
        finally:
            if watcher:
                watcher.destroy()

    def connect(self, device, cancel):
        self._pair_cancelled = False
        if cancel.is_set():
            raise Cancelled()
        self._await(device["path"], "Connect", cancel)

    def disconnect(self, device, cancel):
        if not cancel.is_set():
            call(self.bus, SERVICE, device["path"], DEVICE, "Disconnect")

    def forget(self, device):
        call(self.bus, SERVICE, self.adapter()[0], ADAPTER, "RemoveDevice", "(o)", (device["path"],))

    def trust(self, device, trusted):
        set_prop(self.bus, SERVICE, device["path"], DEVICE, "Trusted", "b", trusted)

    def adapter_option(self, option, enabled):
        path, _ = self.adapter()
        if enabled:
            set_prop(self.bus, SERVICE, path, ADAPTER, option + "Timeout", "u", 120)
        set_prop(self.bus, SERVICE, path, ADAPTER, option, "b", enabled)

    def pair(self, device, menu, cancel=None):
        with private_context():
            return self._pair(device, menu, cancel)

    def _pair(self, device, menu, cancel=None):
        self._pair_cancelled = False
        owner = call(self.bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner", "(s)", (SERVICE,)).unpack()[0]
        notice = notify("Pairing with " + device["name"] + "…", timeout=35000)

        def agent(connection, sender, path, interface, method, parameters, invocation):
            nonlocal notice
            args = parameters.unpack()
            try:
                if sender != owner:
                    invocation.return_dbus_error("org.bluez.Error.Rejected", "Only BlueZ may use this pairing agent.")
                    return
                if args and args[0] != device["path"]:
                    raise Cancelled()
                if method in ["Release", "Cancel"]:
                    invocation.return_value(None)
                elif method == "RequestPinCode":
                    invocation.return_value(GLib.Variant("(s)", (menu.password("Pair Bluetooth", "PIN for " + device["name"], timeout=30),)))
                elif method == "RequestPasskey":
                    invocation.return_value(GLib.Variant("(u)", (int(menu.password("Pair Bluetooth", "Passkey for " + device["name"], numeric=True, timeout=30)),)))
                elif method in ["DisplayPasskey", "DisplayPinCode"]:
                    code = f"{args[1]:06d}" if method == "DisplayPasskey" else args[1]
                    notice = notify(f"Enter {code} on {device['name']} to complete pairing.", notice, timeout=35000)
                    invocation.return_value(None)
                else:
                    message = f"Pair with {device['name']}?"
                    if method == "RequestConfirmation":
                        message += f" Check that the device shows {args[1]:06d}."
                    if not menu.confirm("Pair Bluetooth", message, timeout=30):
                        raise Cancelled()
                    invocation.return_value(None)
            except (Cancelled, ConnectionError):
                self._pair_cancelled = True
                invocation.return_dbus_error("org.bluez.Error.Canceled", "Pairing was cancelled.")

        interface = Gio.DBusNodeInfo.new_for_xml(AGENT_XML).interfaces[0]
        registration = self.bus.register_object(AGENT, interface, agent, None, None)
        registered = False
        try:
            call(self.bus, SERVICE, "/org/bluez", SERVICE + ".AgentManager1", "RegisterAgent", "(os)", (AGENT, "KeyboardDisplay"))
            registered = True
            # Register only for this process; never replace the user's default agent.
            self._await(device["path"], "Pair", cancel)
        finally:
            if registered:
                try:
                    call(self.bus, SERVICE, "/org/bluez", SERVICE + ".AgentManager1", "UnregisterAgent", "(o)", (AGENT,))
                except ConnectionError:
                    pass
            self.bus.unregister_object(registration)
            close_notice(notice)
