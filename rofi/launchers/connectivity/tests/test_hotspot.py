"""Offline hotspot and native-state safety tests; no real sharing is changed.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hotspot
import native_service
import common
from common import Cancelled, ConnectionError, GLib


def state(**changes):
    return {"device": "/device/wifi", "interface": "test-wifi", "profile": "/profile/existing", "uuid": "existing-uuid", "active": True, "active_path": "/active/hotspot", "other_active": "/", "supported": True, "bands": ["", "bg", "a"], "ssid": "Existing hotspot", "raw_ssid": b"Existing hotspot", "band": "bg", "security": "wpa-psk", "shared": True, "upstream": "Mobile broadband", "metered": True, "autoconnect": False, **changes}


def settings():
    return {"connection": {"id": GLib.Variant("s", "Do not rename me"), "uuid": GLib.Variant("s", "existing-uuid"), "type": GLib.Variant("s", "802-11-wireless"), "autoconnect": GLib.Variant("b", False)}, "802-11-wireless": {"mode": GLib.Variant("s", "ap"), "ssid": GLib.Variant("ay", b"Existing hotspot"), "band": GLib.Variant("s", "bg"), "channel": GLib.Variant("u", 6)}, "802-11-wireless-security": {"key-mgmt": GLib.Variant("s", "wpa-psk"), "proto": GLib.Variant("as", ["rsn"])}, "ipv4": {"method": GLib.Variant("s", "shared"), "address-data": GLib.Variant("aa{sv}", [])}, "ipv6": {"method": GLib.Variant("s", "disabled")}}


class HotspotTests(unittest.TestCase):
    def setUp(self):
        self.wifi = Mock()
        self.backend = hotspot.Hotspot(self.wifi)

    def test_adopts_active_profile_without_reading_secrets_or_creating_profiles(self):
        self.wifi.device.return_value = ("/device/wifi", {"Interface": "test-wifi", "ActiveConnection": "/active/hotspot"})
        self.wifi.properties.return_value = {"PrimaryConnection": "/active/mobile", "Metered": 1}
        def properties(bus, service, path, interface):
            if path == "/device/wifi":
                return {"Mode": 3, "WirelessCapabilities": 0x40 | 0x200 | 0x400}
            if path == "/active/hotspot":
                return {"Connection": "/profile/existing", "State": 2}
            return {"Type": "gsm"}
        with patch("hotspot.props", side_effect=properties), patch("hotspot.call", return_value=GLib.Variant("(a{sa{sv}})", (settings(),))) as call:
            result = self.backend.snapshot()
        self.assertTrue(result["active"])
        self.assertEqual(result["profile"], "/profile/existing")
        self.assertEqual(result["uuid"], "existing-uuid")
        self.assertEqual(result["upstream"], "Mobile broadband")
        self.assertEqual(result["bands"], ["", "bg", "a"])
        self.assertEqual([entry.args[4] for entry in call.call_args_list], ["GetSettings"])
        self.wifi.profiles.assert_not_called()

    def test_utf8_name_and_password_validation(self):
        hotspot.validate_settings("網路" * 5, "safe-password", "bg")
        for name, password, band in [("網" * 11, "safe-password", "bg"), ("", "safe-password", "bg"), ("Name", "short", "bg"), ("Name", "safe-password", "6g")]:
            with self.subTest(name=name, band=band), self.assertRaises(ConnectionError):
                hotspot.validate_settings(name, password, band)

    def test_new_profile_is_protected_shared_and_never_autoconnects(self):
        new, old = self.backend._settings(state(profile=None, active=False, band=""), "Private guest", "safe-password", "bg")
        self.assertIsNone(old)
        self.assertFalse(new["connection"]["autoconnect"].unpack())
        self.assertTrue(new["connection"]["permissions"].unpack()[0].startswith("user:"))
        self.assertEqual(new["802-11-wireless-security"]["proto"].unpack(), ["rsn"])
        self.assertEqual(new["802-11-wireless-security"]["pairwise"].unpack(), ["ccmp"])
        self.assertEqual(new["ipv4"]["method"].unpack(), "shared")

    def test_existing_identity_and_password_are_preserved(self):
        with patch("hotspot.call", return_value=GLib.Variant("(a{sa{sv}})", (settings(),))), patch.object(self.backend, "password", return_value="existing-secret"):
            new, previous = self.backend._settings(state(), "New name", None, "a", need_restore=True)
        self.assertEqual(new["connection"]["uuid"].unpack(), "existing-uuid")
        self.assertEqual(new["connection"]["id"].unpack(), "Do not rename me")
        self.assertEqual(new["802-11-wireless-security"]["psk"].unpack(), "existing-secret")
        self.assertNotIn("channel", new["802-11-wireless"])
        self.assertEqual(previous["802-11-wireless"]["ssid"].unpack(), list(b"Existing hotspot"))

    def test_active_edits_require_confirmation_before_any_write(self):
        with patch.object(self.backend, "snapshot", return_value=state()), patch("hotspot.call") as call:
            with self.assertRaises(ConnectionError):
                self.backend.save("New name", None, "bg", threading.Event())
        call.assert_not_called()

    def test_stop_requires_confirmation_and_keeps_profile(self):
        with patch.object(self.backend, "snapshot", return_value=state()), patch("hotspot.call") as call:
            with self.assertRaises(ConnectionError):
                self.backend.stop(threading.Event())
        call.assert_not_called()

    def test_starting_already_active_hotspot_is_a_no_op(self):
        with patch.object(self.backend, "snapshot", return_value=state()), patch("hotspot.call") as call:
            self.backend.start(threading.Event())
        call.assert_not_called()
        self.wifi.set_power.assert_not_called()

    def test_an_external_transition_is_not_restarted(self):
        with patch.object(self.backend, "snapshot", return_value=state(active=False, phase="starting")), patch("hotspot.call") as call:
            with self.assertRaisesRegex(ConnectionError, "in progress"):
                self.backend.start(threading.Event())
        call.assert_not_called()

    def test_starting_over_client_wifi_needs_confirmation(self):
        with patch.object(self.backend, "snapshot", return_value=state(active=False, other_active="/active/client")), patch("hotspot.call") as call:
            with self.assertRaises(ConnectionError):
                self.backend.start(threading.Event())
        call.assert_not_called()

    def test_cancelled_start_does_not_even_create_a_checkpoint(self):
        cancel = threading.Event()
        cancel.set()
        with patch("hotspot.call") as call, self.assertRaises(Cancelled):
            self.backend.start(cancel)
        call.assert_not_called()

    def test_restart_failure_restores_old_settings_and_rolls_back(self):
        current = state()
        with patch.object(self.backend, "snapshot", return_value=current), patch.object(self.backend, "_settings", return_value=({"new": {}}, {"old": {}})), patch.object(self.backend, "_checkpoint", return_value="/checkpoint/ours"), patch.object(self.backend, "_checkpoint_end") as checkpoint, patch.object(self.backend, "_activate", side_effect=ConnectionError("driver failure")), patch("hotspot.call") as call:
            with self.assertRaises(ConnectionError):
                self.backend.save("New name", "safe-password", "a", threading.Event(), restart_confirmed=True)
        methods = [entry.args[4] for entry in call.call_args_list]
        self.assertEqual(methods, ["Update", "DeactivateConnection", "Update"])
        self.assertEqual(call.call_args.args[6], ({"old": {}},))
        checkpoint.assert_called_once_with("/checkpoint/ours", rollback=True)
        self.assertNotIn("Delete", methods)

    def test_rollback_is_attempted_even_if_profile_restore_fails(self):
        def calls(*args):
            if args[4] == "Update" and args[6] == ({"old": {}},):
                raise ConnectionError("restore denied")
        with patch.object(self.backend, "snapshot", return_value=state()), patch.object(self.backend, "_settings", return_value=({"new": {}}, {"old": {}})), patch.object(self.backend, "_checkpoint", return_value="/checkpoint/ours"), patch.object(self.backend, "_checkpoint_end") as checkpoint, patch.object(self.backend, "_activate", side_effect=ConnectionError("failure")), patch("hotspot.call", side_effect=calls):
            with self.assertRaisesRegex(ConnectionError, "recovery"):
                self.backend.save("New name", "safe-password", "a", threading.Event(), restart_confirmed=True)
        checkpoint.assert_called_once_with("/checkpoint/ours", rollback=True)

    def test_unchanged_non_utf8_ssid_bytes_are_not_silently_reencoded(self):
        original = state(ssid="Name�", raw_ssid=b"Name\xff", active=False)
        with patch("hotspot.call", return_value=GLib.Variant("(a{sa{sv}})", (settings(),))), patch.object(self.backend, "password", return_value="existing-secret"):
            changed, _previous = self.backend._settings(original, "Name�", None, "a")
        self.assertEqual(bytes(changed["802-11-wireless"]["ssid"].unpack()), b"Name\xff")

    def test_legacy_security_is_not_silently_converted_or_lost(self):
        with patch("hotspot.call") as call, self.assertRaises(ConnectionError):
            self.backend._settings(state(security="none"), "Existing hotspot", "new-password", "bg")
        call.assert_not_called()

    def test_station_parser_does_not_confuse_traffic_or_signal_fields(self):
        stations = hotspot.parse_stations("Station 02:00:00:00:00:01 (on test-wifi)\n\trx bytes:\t1234\n\ttx bytes:\t5678\n\tsignal:\t-42 [-43, -42] dBm\n\tconnected time:\t91 seconds\n")
        self.assertEqual(stations, [{"mac": "02:00:00:00:00:01", "signal": -42, "rx": 1234, "tx": 5678, "seconds": 91}])

    def test_unavailable_client_statistics_are_not_reported_as_zero(self):
        with patch("hotspot.subprocess.run", return_value=Mock(returncode=1)):
            self.assertIsNone(self.backend.clients(state()))

    def test_wifi_qr_escaping_is_local_and_correct(self):
        payload = hotspot.qr_payload('Cafe: a;b\\c"', 'p;ass:word\\')
        self.assertIn(r'S:Cafe\: a\;b\\c\";', payload)
        self.assertIn(r'P:p\;ass\:word\\;', payload)

    @unittest.skipUnless(importlib.util.find_spec("qrcode"), "Optional python-qrcode is not installed")
    def test_qr_is_generated_in_memory(self):
        self.assertTrue(hotspot.qr_png("Demo only", "demo-password").startswith(b"\x89PNG\r\n\x1a\n"))


class NativeStateTests(unittest.TestCase):
    def service(self):
        service = native_service.NativeService()
        service.wifi = Mock()
        service.bluetooth = Mock()
        service.hotspot = Mock()
        service.hotspot.snapshot.return_value = state()
        service.hotspot.clients.return_value = [Mock(), Mock(), Mock()]
        return service

    @patch("native_service.operation_lock", return_value=nullcontext())
    def test_hotspot_power_off_warning_can_cancel_without_writes(self, lock):
        service = self.service()
        prompts = Mock()
        prompts.confirm.return_value = False
        with self.assertRaises(Cancelled):
            service.perform("wifi_power", {"enabled": False}, prompts, threading.Event())
        service.wifi.set_power.assert_not_called()
        self.assertIn("3 connected", prompts.confirm.call_args.args[1])

    @patch("native_service.operation_lock", return_value=nullcontext())
    def test_stop_sharing_requires_an_affirmative_user_response(self, lock):
        service = self.service()
        prompts = Mock()
        prompts.confirm.return_value = False
        with self.assertRaises(Cancelled):
            service.perform("hotspot_stop", {}, prompts, threading.Event())
        service.hotspot.stop.assert_not_called()

    @patch("native_service.operation_lock", return_value=nullcontext())
    def test_profile_changed_while_editing_cannot_be_overwritten(self, lock):
        service = self.service()
        with self.assertRaises(ConnectionError):
            service.perform("hotspot_save", {"profile": "/different/profile"}, Mock(), threading.Event())
        service.hotspot.save.assert_not_called()

    @patch("native_service.operation_lock", return_value=nullcontext())
    def test_external_setting_changes_are_not_overwritten(self, lock):
        service = self.service()
        with self.assertRaises(ConnectionError):
            service.perform("hotspot_save", {"profile": "/profile/existing", "expected": {"ssid": "Old name", "band": "bg"}}, Mock(), threading.Event())
        service.hotspot.save.assert_not_called()

    @patch("native_service.operation_lock", return_value=nullcontext())
    def test_stale_network_page_cannot_disconnect_running_hotspot(self, lock):
        service = self.service()
        with self.assertRaises(ConnectionError):
            service.perform("wifi_connect", {"path": "/ap/stale"}, Mock(), threading.Event())
        service.wifi.connect.assert_not_called()
        service.hotspot.stop.assert_not_called()

    def test_hotspot_read_does_not_scan_or_fetch_password(self):
        service = self.service()
        service.wifi.powered.return_value = True
        service.bluetooth.powered.return_value = False
        data = service.read()
        self.assertTrue(data["hotspot"]["active"])
        self.assertEqual(data["networks"], [])
        service.wifi.networks.assert_not_called()
        service.hotspot.password.assert_not_called()
        service.wifi.scan.assert_not_called()

    def test_closing_service_never_stops_sharing(self):
        service = self.service()
        service.close()
        service.hotspot.stop.assert_not_called()
        service.wifi.set_power.assert_not_called()

    def test_signal_updates_do_not_move_rows_for_signal_strength_alone(self):
        entries = [{"path": "/second", "connected": False, "profile": None, "strength": 99}, {"path": "/first", "connected": False, "profile": None, "strength": 10}]
        result = native_service.stable_entries(entries, ["/first", "/second"], "networks")
        self.assertEqual([item["path"] for item in result], ["/first", "/second"])
        entries[0]["connected"] = True
        result = native_service.stable_entries(entries, ["/first", "/second"], "networks")
        self.assertEqual(result[0]["path"], "/second")

    def test_authorization_is_never_requested_by_passive_reads(self):
        bus = Mock()
        common.call(bus, "service", "/path", "interface", "GetAll")
        self.assertEqual(bus.call_sync.call_args.args[6], common.Gio.DBusCallFlags.NONE)
        with common.interactive_authorization():
            common.call(bus, "service", "/path", "interface", "Update")
        self.assertEqual(bus.call_sync.call_args.args[6], common.Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION)
        self.assertEqual(common.authorization_flags(), common.Gio.DBusCallFlags.NONE)

    @patch("common.Gio.bus_get_sync", side_effect=AssertionError("Simulation reached a real bus"))
    def test_simulation_has_no_real_backend(self, bus):
        demo = native_service.DemoService()
        self.assertTrue(demo.read()["hotspot"]["active"])
        self.assertEqual(demo.share(), ("Yoru guest", "YoruPreviewOnly2026"))
        bus.assert_not_called()


if __name__ == "__main__":
    unittest.main()
