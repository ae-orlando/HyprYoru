"""Offline safety and presentation regression tests; never operate real radios.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from contextlib import nullcontext
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bluetooth
import common
import menu
import ui
import wifi
from common import Cancelled, ConnectionError, GLib, Row


def network(**changes):
    return {"path": "/ap/1", "device": "/device/wifi", "ssid": b"Home : [5G]", "name": "Home : [5G]", "security": "wpa-psk", "profile": "/profile/saved", "uuid": "saved-uuid", "connected": False, "strength": 80, **changes}


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.backend = wifi.Wifi(bus=object())

    def test_security_types(self):
        for properties, expected in [({}, "open"), ({"Flags": 1}, "wep"), ({"RsnFlags": 256}, "wpa-psk"), ({"RsnFlags": 1024}, "sae"), ({"RsnFlags": 512}, "enterprise"), ({"RsnFlags": 2048}, "owe")]:
            with self.subTest(expected=expected):
                self.assertEqual(wifi.security(properties), expected)

    @patch("wifi.props", return_value={"State": 4})
    @patch("wifi.call", return_value=GLib.Variant("(o)", ("/active/ours",)))
    def test_failed_reconnect_never_deletes_saved_profile(self, call, properties):
        with self.assertRaises(ConnectionError):
            self.backend.connect(network(), None, threading.Event())
        self.assertEqual([item.args[4] for item in call.call_args_list], ["ActivateConnection", "DeactivateConnection"])
        self.assertEqual(call.call_args_list[0].args[6], ("/profile/saved", "/device/wifi", "/ap/1"))

    @patch("wifi.props", return_value={"State": 2})
    @patch("wifi.call", return_value=GLib.Variant("(oo)", ("/profile/new", "/active/new")))
    def test_new_password_uses_dbus_not_process_arguments(self, call, properties):
        ssid = b"Cafe: [5G] \\ <&>\n"
        self.backend.connect(network(profile=None, ssid=ssid), "secret-not-in-argv", threading.Event())
        args = call.call_args.args
        self.assertEqual(args[4], "AddAndActivateConnection")
        settings, device, ap = args[6]
        self.assertEqual(bytes(settings["802-11-wireless"]["ssid"].unpack()), ssid)
        self.assertEqual(settings["802-11-wireless-security"]["psk"].unpack(), "secret-not-in-argv")
        self.assertEqual(ap, "/ap/1")

    @patch("wifi.call")
    def test_cancel_before_connect_has_no_side_effects(self, call):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            self.backend.connect(network(), None, cancel)
        call.assert_not_called()

    @patch("wifi.call", return_value=GLib.Variant("(o)", ("/active/ours",)))
    def test_cancel_deactivates_only_the_new_activation(self, call):
        cancel = threading.Event()
        def activating(*args):
            cancel.set()
            return {"State": 1}
        with patch("wifi.props", side_effect=activating), self.assertRaises(Cancelled):
            self.backend.connect(network(), None, cancel)
        self.assertEqual(call.call_args.args[4], "DeactivateConnection")
        self.assertEqual(call.call_args.args[6], ("/active/ours",))

    @patch("wifi.set_prop")
    def test_hardware_blocked_does_not_try_to_enable(self, setter):
        with patch.object(self.backend, "device"), patch.object(self.backend, "properties", return_value={"WirelessHardwareEnabled": False}):
            with self.assertRaises(ConnectionError):
                self.backend.set_power(True)
        setter.assert_not_called()

    def test_hardware_blocked_is_not_shown_as_on(self):
        with patch.object(self.backend, "device"), patch.object(self.backend, "properties", return_value={"WirelessEnabled": True, "WirelessHardwareEnabled": False}):
            self.assertFalse(self.backend.powered())

    def test_cached_networks_keep_raw_ssids_and_prefer_active_ap(self):
        aps = {
            "/ap/weak": {"Ssid": list(b"Home : [5G]"), "RsnFlags": 256, "Strength": 20},
            "/ap/strong": {"Ssid": list(b"Home : [5G]"), "RsnFlags": 256, "Strength": 99},
            "/ap/other": {"Ssid": list(b"Other"), "Strength": 90},
            "/ap/hidden": {"Ssid": [], "Strength": 100},
        }
        saved = [("/profile/saved", {"connection": {"uuid": "uuid"}, "802-11-wireless": {"ssid": list(b"Home : [5G]")}, "802-11-wireless-security": {"key-mgmt": "wpa-psk"}})]
        def properties(bus, service, path, interface):
            return {"ActiveAccessPoint": "/ap/weak"} if interface == wifi.WIRELESS else aps[path]
        with patch.object(self.backend, "device", return_value=("/device/wifi", {"Interface": "wlan0"})), patch.object(self.backend, "profiles", return_value=saved), patch("wifi.props", side_effect=properties), patch("wifi.call", return_value=GLib.Variant("(ao)", (list(aps),))) as call:
            rows = self.backend.networks()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["path"], "/ap/weak")
        self.assertEqual(rows[0]["ssid"], b"Home : [5G]")
        self.assertEqual(rows[0]["profile"], "/profile/saved")
        self.assertEqual(call.call_args.args[4], "GetAccessPoints")

    def test_password_update_preserves_other_profile_settings(self):
        settings = {"connection": {"id": GLib.Variant("s", "Saved"), "uuid": GLib.Variant("s", "uuid")}, "ipv4": {"method": GLib.Variant("s", "manual")}, "802-11-wireless-security": {"key-mgmt": GLib.Variant("s", "wpa-psk")}}
        reply = GLib.Variant("(a{sa{sv}})", (settings,))
        with patch("wifi.call", side_effect=[reply, GLib.Variant("()", ())]) as call:
            self.backend.password(network(), "replacement-password")
        updated = call.call_args.args[6][0]
        self.assertEqual(updated["ipv4"]["method"].unpack(), "manual")
        self.assertEqual(updated["802-11-wireless-security"]["psk"].unpack(), "replacement-password")

    def test_existing_enterprise_profile_is_reused(self):
        saved = [("/profile/eap", {"connection": {"uuid": "eap-uuid", "interface-name": ""}, "802-11-wireless": {"ssid": list(b"Enterprise")}, "802-11-wireless-security": {"key-mgmt": "wpa-eap"}})]
        def properties(bus, service, path, interface):
            return {"ActiveAccessPoint": "/"} if interface == wifi.WIRELESS else {"Ssid": list(b"Enterprise"), "RsnFlags": 512, "Strength": 80}
        with patch.object(self.backend, "device", return_value=("/device/wifi", {"Interface": "wlan0", "AvailableConnections": ["/profile/eap"]})), patch.object(self.backend, "profiles", return_value=saved), patch("wifi.props", side_effect=properties), patch("wifi.call", return_value=GLib.Variant("(ao)", (["/ap/eap"],))):
            self.assertEqual(self.backend.networks()[0]["profile"], "/profile/eap")

    @patch("wifi.call")
    def test_new_enterprise_network_requires_advanced_setup(self, call):
        with self.assertRaises(ConnectionError):
            self.backend.connect(network(profile=None, security="enterprise"), None, threading.Event())
        call.assert_not_called()


class BluetoothTests(unittest.TestCase):
    def setUp(self):
        self.backend = bluetooth.Bluetooth(bus=Mock())

    def test_input_device_detection(self):
        self.assertTrue(bluetooth.input_device({"Icon": "input-keyboard"}))
        self.assertTrue(bluetooth.input_device({"UUIDs": ["00001812-0000-1000-8000-00805f9b34fb"]}))
        self.assertFalse(bluetooth.input_device({"Icon": "audio-headphones"}))

    @patch("bluetooth.call")
    def test_scan_stops_only_its_own_discovery_session(self, call):
        cancel = Mock()
        cancel.is_set.return_value = False
        cancel.wait.return_value = False
        with patch.object(self.backend, "adapter", return_value=("/org/bluez/hci0", {"Discovering": True})):
            self.backend.scan(cancel)
        self.assertEqual([item.args[4] for item in call.call_args_list], ["StartDiscovery", "StopDiscovery"])

    @patch("bluetooth.call", side_effect=ConnectionError("no permission"))
    def test_failed_scan_does_not_stop_another_clients_scan(self, call):
        with patch.object(self.backend, "adapter", return_value=("/org/bluez/hci0", {})), self.assertRaises(ConnectionError):
            self.backend.scan(threading.Event())
        self.assertEqual([item.args[4] for item in call.call_args_list], ["StartDiscovery"])

    @patch("bluetooth.call")
    def test_scan_cancellation_still_releases_discovery(self, call):
        cancel = Mock()
        cancel.is_set.return_value = False
        cancel.wait.return_value = True
        with patch.object(self.backend, "adapter", return_value=("/org/bluez/hci0", {})), self.assertRaises(Cancelled):
            self.backend.scan(cancel)
        self.assertEqual(call.call_args.args[4], "StopDiscovery")

    def test_missing_adapter_is_reported(self):
        with patch.object(self.backend, "objects", return_value={}), self.assertRaises(ConnectionError):
            self.backend.adapter()

    @patch("bluetooth.set_prop")
    def test_discoverability_is_explicit_and_time_limited(self, setter):
        with patch.object(self.backend, "adapter", return_value=("/org/bluez/hci0", {})):
            self.backend.adapter_option("Discoverable", True)
        self.assertEqual(setter.call_args_list[0].args[-3:], ("DiscoverableTimeout", "u", 120))
        self.assertEqual(setter.call_args_list[1].args[-3:], ("Discoverable", "b", True))

    def test_async_connect_finishes_and_releases_its_cancel_watcher(self):
        class Bus:
            def call(self, *args):
                self.arguments = args
                GLib.idle_add(lambda: (args[-1](self, object(), None), False)[1])
            def call_finish(self, result):
                return GLib.Variant("()", ())
        bus = Bus()
        backend = bluetooth.Bluetooth(bus=bus)
        backend.connect({"path": "/selected/device"}, threading.Event())
        self.assertEqual(bus.arguments[:4], ("org.bluez", "/selected/device", "org.bluez.Device1", "Connect"))

    @patch("bluetooth.notify", return_value=42)
    @patch("bluetooth.close_notice")
    def test_pairing_agent_rejects_an_untrusted_caller(self, close_notice, notify):
        device = {"path": "/org/bluez/hci0/dev_00", "name": "Headphones"}
        ui = Mock()
        self.backend.bus.register_object.return_value = 7
        invocation = Mock()
        def exchange(*args):
            handler = self.backend.bus.register_object.call_args.args[2]
            handler(None, ":attacker", bluetooth.AGENT, "org.bluez.Agent1", "RequestPinCode", GLib.Variant("(o)", (device["path"],)), invocation)
        with patch("bluetooth.call", return_value=GLib.Variant("(s)", (":bluez",))) as call, patch.object(self.backend, "_await", side_effect=exchange):
            self.backend.pair(device, ui)
        invocation.return_dbus_error.assert_called_once()
        ui.password.assert_not_called()
        self.backend.bus.unregister_object.assert_called_once_with(7)
        self.assertNotIn("RequestDefaultAgent", [item.args[4] for item in call.call_args_list])
        close_notice.assert_called_once_with(42)

    @patch("bluetooth.notify", return_value=0)
    @patch("bluetooth.close_notice")
    def test_pairing_rejects_a_different_device(self, close_notice, notify):
        ui = Mock()
        invocation = Mock()
        def exchange(*args):
            handler = self.backend.bus.register_object.call_args.args[2]
            handler(None, ":bluez", bluetooth.AGENT, "org.bluez.Agent1", "RequestPinCode", GLib.Variant("(o)", ("/other/device",)), invocation)
        with patch("bluetooth.call", return_value=GLib.Variant("(s)", (":bluez",))), patch.object(self.backend, "_await", side_effect=exchange):
            self.backend.pair({"path": "/expected/device", "name": "Expected"}, ui)
        ui.password.assert_not_called()
        self.assertTrue(self.backend._pair_cancelled)

    @patch("bluetooth.notify", return_value=0)
    @patch("bluetooth.close_notice")
    def test_pairing_confirmation_cancel_never_authorizes(self, close_notice, notify):
        ui = Mock()
        ui.confirm.return_value = False
        invocation = Mock()
        def exchange(*args):
            handler = self.backend.bus.register_object.call_args.args[2]
            handler(None, ":bluez", bluetooth.AGENT, "org.bluez.Agent1", "RequestConfirmation", GLib.Variant("(ou)", ("/expected/device", 123456)), invocation)
        with patch("bluetooth.call", return_value=GLib.Variant("(s)", (":bluez",))), patch.object(self.backend, "_await", side_effect=exchange):
            self.backend.pair({"path": "/expected/device", "name": "Expected"}, ui)
        invocation.return_value.assert_not_called()
        invocation.return_dbus_error.assert_called_once()
        self.assertTrue(self.backend._pair_cancelled)


class ControllerTests(unittest.TestCase):
    def app(self, radio="wifi"):
        return menu.Connections(radio, backend=Mock(), ui=Mock())

    def test_forget_requires_explicit_confirmation(self):
        app = self.app()
        app.entries["/ap/1"] = network()
        app.ui.confirm.return_value = False
        app.perform(Row("Forget", "forget", "/ap/1"))
        app.backend.forget.assert_not_called()
        app.ui.confirm.return_value = True
        app.perform(Row("Forget", "forget", "/ap/1"))
        app.backend.forget.assert_called_once_with(app.entries["/ap/1"])

    def test_password_cancellation_does_not_connect(self):
        app = self.app()
        app.entries["/ap/1"] = network(profile=None)
        app.ui.password.side_effect = Cancelled()
        with self.assertRaises(Cancelled):
            app.perform(Row("Connect", "connect", "/ap/1"))
        app.ui.work.assert_not_called()
        app.backend.connect.assert_not_called()

    def test_bluetooth_power_off_protects_input_devices(self):
        app = self.app("bluetooth")
        app.backend.connected_inputs.return_value = ["Keyboard"]
        app.ui.confirm.return_value = False
        with self.assertRaises(Cancelled):
            app.power(False)
        app.backend.set_power.assert_not_called()

    def test_root_uses_cached_results_without_scanning(self):
        app = self.app()
        app.backend.powered.return_value = True
        app.backend.networks.return_value = [network()]
        title, status, rows = app.root()
        app.backend.scan.assert_not_called()
        self.assertEqual(rows[0].target, "/ap/1")
        self.assertTrue(any(row.action == "scan" for row in rows))

    def test_back_keeps_the_root_search_state_key(self):
        app = self.app()
        app.backend.powered.return_value = True
        app.backend.networks.return_value = [network()]
        app.ui.choose.side_effect = [Row("Network", "details", "/ap/1"), Row("Back", "back"), Cancelled()]
        app.run()
        self.assertEqual([item.kwargs["key"] for item in app.ui.choose.call_args_list], ["root", "details/ap/1", "root"])

    def test_long_names_do_not_become_the_dialog_title(self):
        app = self.app()
        app.target = "/ap/1"
        app.backend.networks.return_value = [network(name="A" * 100)]
        title, message, rows = app.details()
        self.assertEqual(title, "Network")
        self.assertIn("A" * 100, message)

    def test_cancel_feedback_keeps_the_selected_network_visible(self):
        app = self.app()
        app.view = "details"
        app.target = "/ap/1"
        app.message = "Cancelled"
        app.backend.networks.return_value = [network()]
        app.ui.choose.side_effect = Cancelled()
        app.run()
        message = app.ui.choose.call_args.args[1]
        self.assertIn("Home : [5G]", message)
        self.assertIn("Cancelled", message)

    @patch("menu.operation_lock", return_value=nullcontext())
    def test_power_command_is_explicit_not_a_blind_toggle(self, lock):
        app = self.app()
        app.dispatch(Row("On", "power_on"))
        app.backend.set_power.assert_called_once_with(True)


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.ui = ui.Menu.__new__(ui.Menu)
        self.ui.theme = Path("/theme.rasi")
        self.ui.positions = {}
        self.ui.placement = []

    @patch("ui.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "1\x1fHome\n", ""))
    def test_duplicate_labels_dispatch_by_selected_index(self, run):
        rows = [Row("Same [name]", "details", "/device/one"), Row("Same [name]", "details", "/device/two")]
        result = self.ui.choose("Devices", "<&>", rows)
        self.assertEqual(result.target, "/device/two")
        args = run.call_args.args[0]
        self.assertIn("&lt;&amp;&gt;", args)
        self.assertNotIn("-markup-rows", args)
        self.assertEqual(self.ui.positions["Devices"], (1, "Home"))

    @patch("ui.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", ""))
    def test_escape_does_not_choose_an_action(self, run):
        with self.assertRaises(Cancelled):
            self.ui.choose("Wi-Fi", "", [Row("Power", "power_off")])

    @patch("ui.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", ""))
    def test_empty_password_is_cancellation(self, run):
        with self.assertRaises(Cancelled):
            self.ui.password("Password", "Network")

    @patch("ui.subprocess.run", side_effect=subprocess.TimeoutExpired("rofi", 30))
    def test_pairing_prompt_timeout_is_cancellation(self, run):
        with self.assertRaises(Cancelled):
            self.ui.password("Pair", "PIN", timeout=30)

    @patch("ui.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "99\x1f\n", ""))
    def test_invalid_selection_never_dispatches_a_row(self, run):
        with self.assertRaises(ConnectionError):
            self.ui.choose("Wi-Fi", "", [Row("Off", "power_off")])

    @patch("ui.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "1\x1fCafe\n", ""))
    def test_restored_filter_cannot_select_a_hidden_original_row(self, run):
        self.ui.positions["Wi-Fi"] = (0, "Cafe")
        result = self.ui.choose("Wi-Fi", "", [Row("Other", "details", "wrong"), Row("Cafe", "details", "right")])
        self.assertEqual(result.target, "right")
        self.assertNotIn("-selected-row", run.call_args.args[0])

    @patch("ui.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "0\x1f\n", ""))
    def test_navigation_and_refresh_remain_visible_while_searching(self, run):
        self.ui.choose("Wi-Fi", "", [Row("Refresh", "scan"), Row("Back", "exit")])
        self.assertEqual(run.call_args.kwargs["input"].count("permanent\x1ftrue"), 2)

    def test_long_unicode_messages_have_explicit_safe_lines(self):
        command = self.ui.command("Wi-Fi", "網路 <&> " * 30)
        value = command[command.index("-mesg") + 1]
        self.assertIn("\n", value)
        self.assertIn("&lt;&amp;&gt;", value)

    @patch("ui.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "0\x1f\n", ""))
    def test_confirmation_defaults_to_cancel_and_clears_selection(self, run):
        self.assertFalse(self.ui.confirm("Forget?", "Saved network"))
        self.assertTrue(run.call_args.kwargs["input"].startswith("Cancel"))
        self.assertNotIn("confirmation", self.ui.positions)

    def test_control_characters_cannot_create_extra_menu_rows(self):
        self.assertEqual(common.text("SSID\nname\0data"), "SSID name data")

    def test_runtime_lock_is_private(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"XDG_RUNTIME_DIR": directory}):
            with common.operation_lock("wifi"):
                self.assertEqual((Path(directory) / "yoru-connections").stat().st_mode & 0o777, 0o700)

    def test_runtime_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unsafe").symlink_to(root / "destination")
            (root / "destination").mkdir(mode=0o700)
            with patch.dict("os.environ", {"XDG_RUNTIME_DIR": str(root / "unsafe")}), self.assertRaises(ConnectionError):
                with common.operation_lock("wifi"):
                    self.fail("An unsafe runtime path was accepted")


class CommandTests(unittest.TestCase):
    @patch("menu.operation_lock", return_value=nullcontext())
    @patch("menu.Wifi")
    def test_swaync_requested_state_is_idempotent(self, factory, lock):
        self.assertEqual(menu.main(["wifi", "--power", "true"]), 0)
        factory.return_value.set_power.assert_called_once_with(True)
        factory.return_value.powered.assert_not_called()

    @patch("menu.Wifi", side_effect=ConnectionError("service unavailable"))
    def test_unavailable_radio_state_is_false_without_notifications(self, factory):
        with patch("sys.stdout", new_callable=io.StringIO) as output, patch("menu.notify") as notify:
            self.assertEqual(menu.main(["wifi", "--state"]), 0)
        self.assertEqual(output.getvalue(), "false\n")
        notify.assert_not_called()

    @patch("menu.operation_lock", return_value=nullcontext())
    @patch("menu.Bluetooth")
    @patch("menu.Menu")
    @patch("menu.panel_visible", return_value=True)
    @patch("menu.panel")
    @patch("menu.notify")
    def test_input_warning_cancel_refreshes_only_once(self, notify, panel, visible, ui, backend, lock):
        backend.return_value.connected_inputs.return_value = ["Keyboard"]
        ui.return_value.confirm.return_value = False
        self.assertEqual(menu.main(["bluetooth", "--power", "false", "--from-swaync"]), 0)
        self.assertEqual([item.args for item in panel.call_args_list], [(False,), (True,)])
        backend.return_value.set_power.assert_not_called()
        notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
