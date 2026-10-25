#!/usr/bin/env python3
"""Network indicator regression fixtures; no real radios or credentials.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("yoru_network", Path(__file__).parents[1] / "network.py")
network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(network)


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.data = {(network.ROOT, network.SERVICE): {
            "NetworkingEnabled": True, "WirelessEnabled": True, "WirelessHardwareEnabled": True,
            "Devices": ["/wifi"], "PrimaryConnection": "/active-wifi"},
            ("/wifi", network.DEVICE): {"DeviceType": 2, "State": 100, "Interface": "wlan0", "ActiveConnection": "/active-wifi"},
            ("/wifi", network.WIRELESS): {"Mode": 2, "ActiveAccessPoint": "/ap"},
            ("/ap", network.AP): {"Ssid": b"Synthetic network", "Strength": 78}}
        self.calls = []

    def read(self, path, interface):
        self.calls.append((path, interface))
        self.assertIn(interface, [network.SERVICE, network.DEVICE, network.WIRELESS, network.AP, network.ACTIVE])
        if (path, interface) not in self.data:
            raise network.ConnectionError("Fixture object disappeared")
        return self.data[path, interface]

    def test_wifi_is_a_stable_icon_with_details_only_in_tooltip(self):
        status = network.snapshot(self.read)
        self.assertEqual(status["alt"], "wifi")
        self.assertIn("connected", status["class"])
        self.assertNotIn("Synthetic", status["text"])
        self.assertIn("Synthetic network", status["tooltip"])
        self.assertIn("78%", status["tooltip"])

    def test_hotspot_is_not_misidentified_as_ethernet(self):
        self.data["/wifi", network.WIRELESS]["Mode"] = 3
        status = network.snapshot(self.read)
        self.assertEqual(status["alt"], "hotspot")
        self.assertIn("No upstream", status["tooltip"])
        self.assertNotIn(("/ap", network.AP), self.calls)

    def test_hotspot_with_ethernet_uplink_keeps_sharing_visible(self):
        self.data["/wifi", network.WIRELESS]["Mode"] = 3
        self.data[network.ROOT, network.SERVICE]["PrimaryConnection"] = "/wired-connection"
        self.data["/wired-connection", network.ACTIVE] = {"Type": "802-3-ethernet"}
        status = network.snapshot(self.read)
        self.assertEqual(status["alt"], "hotspot")
        self.assertIn("Ethernet uplink", status["tooltip"])

    def test_markup_and_control_characters_are_literal(self):
        self.data["/ap", network.AP]["Ssid"] = b"<b>untrusted</b>\n&network"
        status = network.snapshot(self.read)
        self.assertIn("&lt;b&gt;untrusted&lt;/b&gt; &amp;network", status["tooltip"])

    def test_long_unicode_names_are_bounded(self):
        self.assertLess(len(network.literal("夜" * 1000)), 90)

    def test_wireless_off_is_distinct_from_disconnected(self):
        self.data["/wifi", network.DEVICE]["State"] = 30
        self.data[network.ROOT, network.SERVICE]["WirelessEnabled"] = False
        self.assertEqual(network.snapshot(self.read)["tooltip"], "Wi-Fi off")
        self.data[network.ROOT, network.SERVICE]["WirelessEnabled"] = True
        self.assertEqual(network.snapshot(self.read)["alt"], "idle")

    def test_hardware_block_and_networking_disabled(self):
        self.data["/wifi", network.DEVICE]["State"] = 30
        self.data[network.ROOT, network.SERVICE]["WirelessHardwareEnabled"] = False
        self.assertIn("hardware blocked", network.snapshot(self.read)["tooltip"])
        self.data[network.ROOT, network.SERVICE]["NetworkingEnabled"] = False
        self.assertEqual(network.snapshot(self.read)["tooltip"], "Networking disabled")

    def test_hotspot_starting_is_not_reported_active(self):
        self.data["/wifi", network.DEVICE]["State"] = 50
        self.data["/wifi", network.WIRELESS]["Mode"] = 3
        status = network.snapshot(self.read)
        self.assertIn("connecting", status["class"])
        self.assertNotIn("connected", status["class"])

    def test_missing_access_point_does_not_hide_connected_wifi(self):
        del self.data["/ap", network.AP]
        self.assertIn("connected", network.snapshot(self.read)["class"])

    def test_wired_connection_stays_visible_with_wifi_disabled(self):
        self.data[network.ROOT, network.SERVICE].update({"Devices": ["/wired"], "PrimaryConnection": "/wired-connection", "WirelessEnabled": False})
        self.data["/wired", network.DEVICE] = {"DeviceType": 1, "State": 100, "ActiveConnection": "/wired-connection", "Interface": "eth0"}
        self.assertEqual(network.snapshot(self.read)["alt"], "ethernet")

    def test_vpn_route_does_not_hide_physical_link(self):
        self.data[network.ROOT, network.SERVICE]["Devices"].append("/vpn")
        self.data[network.ROOT, network.SERVICE]["PrimaryConnection"] = "/vpn-connection"
        self.data["/vpn", network.DEVICE] = {"DeviceType": 29, "State": 100, "ActiveConnection": "/vpn-connection"}
        self.assertEqual(network.snapshot(self.read)["alt"], "wifi")

    def test_disappearing_device_and_no_adapters_are_safe(self):
        del self.data["/wifi", network.DEVICE]
        self.assertEqual(network.snapshot(self.read)["alt"], "disconnected")

    def test_loopback_is_not_a_working_network_connection(self):
        self.data[network.ROOT, network.SERVICE]["Devices"].append("/loopback")
        self.data["/wifi", network.DEVICE]["State"] = 30
        self.data["/loopback", network.DEVICE] = {"DeviceType": 32, "State": 100, "Interface": "lo"}
        self.assertEqual(network.snapshot(self.read)["alt"], "idle")

    def test_unrouted_container_bridge_is_not_a_working_uplink(self):
        self.data[network.ROOT, network.SERVICE].update({"PrimaryConnection": "/", "Devices": ["/bridge"]})
        self.data["/bridge", network.DEVICE] = {"DeviceType": 13, "State": 100, "Interface": "docker0", "ActiveConnection": "/bridge-connection"}
        self.assertEqual(network.snapshot(self.read)["alt"], "disconnected")


if __name__ == "__main__":
    unittest.main()
