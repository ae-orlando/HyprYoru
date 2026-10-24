"""Compact copy and input-modality regressions; no real radio operations.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from presentation import client_name, connected_text, elapsed_text, security_text, signal_icon


class PresentationTests(unittest.TestCase):
    def test_counts_are_natural_not_template_copy(self):
        self.assertEqual(connected_text(1), "1 connected")
        self.assertEqual(connected_text(3), "3 connected")
        self.assertEqual(connected_text(None), "Devices unavailable")

    def test_security_labels_are_human_readable(self):
        self.assertEqual(security_text("wpa-psk"), "Secured")
        self.assertEqual(security_text("sae"), "WPA3")
        self.assertEqual(security_text("open"), "Open")

    def test_unknown_clients_still_have_distinct_identifiers(self):
        client = {"name": "Connected device", "ip": "10.42.0.23", "mac": "02:00:00:00:aa:bb"}
        self.assertEqual(client_name(client), "10.42.0.23")
        client["ip"] = ""
        self.assertEqual(client_name(client), "Device · AA:BB")
        client["name"] = "Guest phone"
        self.assertEqual(client_name(client), "Guest phone")

    def test_signal_strength_uses_quiet_visual_indicators(self):
        self.assertIn("excellent", signal_icon(-41))
        self.assertIn("weak", signal_icon(-85))
        self.assertIn("none", signal_icon(None))

    def test_elapsed_time_is_compact(self):
        self.assertEqual(elapsed_text(13), "13s")
        self.assertEqual(elapsed_text(125), "2m")
        self.assertEqual(elapsed_text(3720), "1h 2m")


class FocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from drawer import Drawer, Gdk
        cls.drawer = Drawer
        cls.gdk = Gdk

    def test_mouse_interaction_hides_focus_without_disrupting_text_editing(self):
        window = Mock()
        self.drawer.pointer_input(window)
        self.assertEqual(window.input_mode, "pointer")
        window.remove_css_class.assert_called_once_with("keyboard-nav")
        window.set_focus_visible.assert_called_once_with(False)
        window.set_focus.assert_not_called()

    def test_open_does_not_remove_keyboard_navigation_focus(self):
        window = Mock(input_mode="keyboard", closed=False)
        self.drawer.reset_open_focus(window)
        window.set_focus.assert_not_called()

    def test_open_does_not_clear_a_password_dialog(self):
        window = Mock(input_mode="pointer", closed=False)
        window.get_visible_dialog.return_value = object()
        self.drawer.reset_open_focus(window)
        window.set_focus.assert_not_called()

    def test_pointer_open_has_no_remembered_control(self):
        window = Mock(input_mode="pointer", closed=False)
        window.get_visible_dialog.return_value = None
        self.drawer.reset_open_focus(window)
        window.set_focus_visible.assert_called_once_with(False)
        window.set_focus.assert_called_once_with(None)

    def test_modifier_keys_do_not_create_a_navigation_highlight(self):
        window = Mock(input_mode="pointer")
        self.drawer.on_key(window, None, self.gdk.KEY_Shift_L, 0, self.gdk.ModifierType.SHIFT_MASK)
        self.assertEqual(window.input_mode, "pointer")
        window.add_css_class.assert_not_called()
        window.set_focus_visible.assert_not_called()


if __name__ == "__main__":
    unittest.main()
