#!/usr/bin/env python
"""On-demand native Yoru Connections drawer; --demo never touches real radios.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

# GTK4 Layer Shell must be loaded before GTK/libwayland-client (upstream's
# Python bootstrap requirement), not merely imported after libadwaita.
from ctypes import CDLL
from ctypes.util import find_library
CDLL(find_library("gtk4-layer-shell") or "libgtk4-layer-shell.so")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Gtk4LayerShell as Layer, Pango

from common import Cancelled, ConnectionError, panel, text
from hotspot import engaged, generate_password, qr_png
from native_service import DemoService, NativeService, stable_entries
from presentation import client_name, connected_text, elapsed_text, security_text, signal_icon


def label(value="", css=None, wrap=False):
    widget = Gtk.Label(label=text(value), xalign=0, wrap=wrap)
    widget.set_hexpand(True)
    if not wrap:
        widget.set_ellipsize(Pango.EllipsizeMode.END)
    else:
        widget.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        widget.set_max_width_chars(36)
    if css:
        widget.add_css_class(css)
    return widget


def button(title=None, icon=None, callback=None, css=None):
    widget = Gtk.Button(label=title) if title else Gtk.Button(icon_name=icon)
    widget.set_focus_on_click(False)
    if callback:
        widget.connect("clicked", lambda *_args: callback())
    if css:
        widget.add_css_class(css)
    return widget


def size_text(value):
    for suffix in ["B", "KB", "MB", "GB"]:
        if value < 1024 or suffix == "GB":
            return f"{value:.0f} {suffix}" if suffix == "B" else f"{value:.1f} {suffix}"
        value /= 1024


def idle_once(function):
    """GTK methods may return True; never let that repeat an idle callback."""
    def invoke():
        function()
        return False
    return GLib.idle_add(invoke, priority=GLib.PRIORITY_DEFAULT)


class Prompts:
    """Bridge backend workers to nonblocking GTK dialogs on the GTK thread."""
    def __init__(self, window, cancel):
        self.window = window
        self.cancel = cancel

    def request(self, title, message, secret=False, numeric=False, timeout=60):
        done = threading.Event()
        answer = []
        holder = []

        def show():
            if self.window.closed:
                done.set()
                return False
            dialog = Adw.AlertDialog(heading=text(title), body=text(message))
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("ok", "Continue" if not secret else "Submit")
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")
            danger = any(word in title.lower() for word in ["forget", "stop", "off", "disconnect", "restart"])
            dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE if danger else Adw.ResponseAppearance.SUGGESTED)
            entry = None
            if secret:
                entry = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True)
                entry.add_css_class("secret-entry")
                dialog.set_extra_child(entry)
                dialog.set_response_enabled("ok", False)
                entry.connect("changed", lambda *_args: dialog.set_response_enabled("ok", bool(entry.get_text()) and (not numeric or (entry.get_text().isascii() and entry.get_text().isdigit() and len(entry.get_text()) <= 6))))

            def response(_dialog, result):
                if result == "ok":
                    answer.append(entry.get_text() if entry else True)
                if entry:
                    entry.set_text("")
                done.set()

            dialog.connect("response", response)
            holder.append(dialog)
            dialog.present(self.window)
            if entry:
                entry.grab_focus()
            return False

        GLib.idle_add(show, priority=GLib.PRIORITY_DEFAULT)
        deadline = time.monotonic() + (timeout or 60)
        while not done.wait(0.05):
            if self.cancel.is_set() or self.window.closed or time.monotonic() >= deadline:
                if holder:
                    dialog = holder[0]
                    idle_once(lambda: dialog.close() if self.window.get_visible_dialog() == dialog else None)
                raise Cancelled()
        if not answer:
            raise Cancelled()
        return answer[0]

    def confirm(self, title, message, timeout=60):
        try:
            return self.request(title, message, timeout=timeout)
        except Cancelled:
            return False

    def password(self, title, message, numeric=False, timeout=60):
        return self.request(title, message, secret=True, numeric=numeric, timeout=timeout)


class Drawer(Adw.ApplicationWindow):
    def __init__(self, app, service, page="wifi", origin=False, demo=False):
        super().__init__(application=app, title="Yoru Connections")
        self.app = app
        self.add_css_class("connections-window")
        self.service = service
        self.origin = origin
        self.demo = demo
        self.page = page
        self.closed = False
        self.visibility_generation = 0
        self.busy = False
        self.reading = False
        self.updating = False
        self.input_mode = "pointer"
        self.dirty = False
        self.data = {}
        self.form_profile = None
        self.form_revision = None
        self.band_ids = [""]
        self.row_maps = {}
        self.cancel = threading.Event()
        self.refresh_source = 0
        self.detail_target = None
        self.detail_signature = None
        self.client_value_labels = {}
        self.watched = False
        Layer.init_for_window(self)
        Layer.set_namespace(self, "yoru-connections-demo" if demo else "yoru-connections")
        Layer.set_layer(self, Layer.Layer.OVERLAY)
        Layer.set_keyboard_mode(self, Layer.KeyboardMode.EXCLUSIVE)
        Layer.set_anchor(self, Layer.Edge.TOP, True)
        Layer.set_anchor(self, Layer.Edge.RIGHT, True)
        Layer.set_margin(self, Layer.Edge.TOP, 14)
        Layer.set_margin(self, Layer.Edge.RIGHT, 14)
        self.set_default_size(420, -1)

        self.backdrop = Gtk.ApplicationWindow(application=app)
        self.backdrop.add_css_class("connections-backdrop")
        Layer.init_for_window(self.backdrop)
        Layer.set_namespace(self.backdrop, "yoru-connections-backdrop")
        Layer.set_layer(self.backdrop, Layer.Layer.TOP)
        Layer.set_keyboard_mode(self.backdrop, Layer.KeyboardMode.NONE)
        for edge in [Layer.Edge.TOP, Layer.Edge.BOTTOM, Layer.Edge.LEFT, Layer.Edge.RIGHT]:
            Layer.set_anchor(self.backdrop, edge, True)
        background = Gtk.Box(hexpand=True, vexpand=True)
        gesture = Gtk.GestureClick()
        gesture.connect("released", lambda *_args: self.close())
        background.add_controller(gesture)
        self.backdrop.set_child(background)

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        shell.add_css_class("drawer-shell")
        self.set_content(shell)
        header = Gtk.Box(spacing=8)
        header.add_css_class("drawer-header")
        self.back = button(icon="go-previous-symbolic", callback=self.go_back, css="header-button")
        self.back.set_tooltip_text("Back to Wi-Fi / quick settings")
        header.append(self.back)
        self.header_title = label("Connections", "drawer-title")
        header.append(self.header_title)
        if demo:
            header.append(label("PREVIEW", "badge"))
        header.append(button(icon="window-close-symbolic", callback=self.close, css="header-button"))
        shell.append(header)

        tabs = Gtk.Box(spacing=6, homogeneous=True)
        tabs.add_css_class("page-tabs")
        self.tabs = {}
        for name, title in [("wifi", "Wi-Fi"), ("bluetooth", "Bluetooth")]:
            tab = Gtk.ToggleButton(label=title, hexpand=True)
            tab.set_focus_on_click(False)
            tab.connect("clicked", lambda _widget, value=name: self.navigate(value))
            tabs.append(tab)
            self.tabs[name] = tab
        shell.append(tabs)

        self.progress = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        progress_box = Gtk.Box(spacing=10)
        progress_box.add_css_class("operation")
        self.spinner = Gtk.Spinner(spinning=True)
        progress_box.append(self.spinner)
        self.progress_text = label("Working…", wrap=True)
        progress_box.append(self.progress_text)
        progress_box.append(button("Cancel", callback=lambda: self.cancel.set(), css="quiet-button"))
        self.progress.set_child(progress_box)
        shell.append(self.progress)

        self.error = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        error_box = Gtk.Box(spacing=8)
        error_box.add_css_class("error-banner")
        self.error_text = label("", wrap=True)
        error_box.append(self.error_text)
        error_box.append(button(icon="window-close-symbolic", callback=lambda: self.error.set_reveal_child(False)))
        self.error.set_child(error_box)
        shell.append(self.error)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=180, vhomogeneous=False)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True, max_content_height=720)
        display = self.get_display()
        monitors = display.get_monitors()
        if monitors.get_n_items():
            monitor = monitors.get_item(0)
            try:
                result = subprocess.run(["hyprctl", "-j", "monitors"], capture_output=True, text=True, timeout=2, check=True)
                connector = next(item["name"] for item in json.loads(result.stdout) if item["focused"])
                monitor = next((monitors.get_item(index) for index in range(monitors.get_n_items()) if monitors.get_item(index).get_connector() == connector), monitor)
            except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
                pass
            available = monitor.get_geometry().height - 220
            scroll.set_max_content_height(max(300, min(720, available)))
            Layer.set_monitor(self, monitor)
            Layer.set_monitor(self.backdrop, monitor)
        scroll.set_child(self.stack)
        shell.append(scroll)
        self.build_wifi()
        self.build_bluetooth()
        self.build_hotspot()
        self.build_hotspot_editor()
        self.build_details()
        self.set_controls()
        self.navigate(page)
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)
        pointer = Gtk.GestureClick()
        pointer.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        pointer.connect("pressed", lambda *_args: self.pointer_input())
        self.add_controller(pointer)
        self.connect("close-request", self.on_close)
        self.poll_source = GLib.timeout_add_seconds(3, self.poll_clients)
        self.backdrop.present()
        self.present()
        idle_once(self.reset_open_focus)
        self.request_read()

    def new_page(self, name):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.add_css_class("page-content")
        self.stack.add_named(content, name)
        return content

    def section(self, content, title):
        content.append(label(title, "section-label"))
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        content.append(box)
        return box

    def action_row(self, title, subtitle="", icon=None):
        row = Adw.ActionRow(title=text(title), subtitle=text(subtitle), use_markup=False)
        row.set_title_lines(1)
        row.set_subtitle_lines(2)
        row.set_focus_on_click(False)
        if icon:
            image = Gtk.Image(icon_name=icon, pixel_size=20)
            image.add_css_class("row-icon")
            row.add_prefix(image)
        return row

    def radio(self, content, title, action):
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        box.add_css_class("radio-list")
        icons = {"wifi_power": "network-wireless-symbolic", "bt_power": "bluetooth-symbolic", "hotspot_power": "network-transmit-receive-symbolic"}
        row = self.action_row(title, "Checking adapter…", icons[action])
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        switch.set_focus_on_click(False)
        switch.connect("state-set", lambda widget, state: self.radio_request(widget, state, action))
        row.add_suffix(switch)
        box.append(row)
        content.append(box)
        return row, switch

    def build_wifi(self):
        content = self.new_page("wifi")
        self.wifi_row, self.wifi_switch = self.radio(content, "Wi-Fi", "wifi_power")
        self.wifi_hero = Gtk.Box(spacing=12)
        self.wifi_hero.add_css_class("connection-summary")
        self.wifi_hero.append(Gtk.Image(icon_name="network-wireless-symbolic", pixel_size=24))
        description = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
        self.wifi_headline = label("Connecting…", "summary-title", wrap=True)
        self.wifi_description = label("", "summary-subtitle", wrap=True)
        description.append(self.wifi_headline)
        description.append(self.wifi_description)
        self.wifi_hero.append(description)
        self.manage_hotspot = button("Hotspot ›", callback=lambda: self.navigate("hotspot"), css="quiet-button")
        self.manage_hotspot.set_valign(Gtk.Align.CENTER)
        self.wifi_hero.append(self.manage_hotspot)
        content.append(self.wifi_hero)
        tools = Gtk.Box(spacing=8)
        self.network_tools = tools
        tools.append(label("Networks", "section-label"))
        search = button(icon="system-search-symbolic", callback=lambda: self.reveal_search("wifi"), css="header-button")
        search.set_tooltip_text("Search networks · Ctrl+F")
        tools.append(search)
        self.scan_wifi = button(icon="view-refresh-symbolic", callback=lambda: self.run_action("wifi_scan", {}, "Refreshing nearby networks…"), css="header-button")
        self.scan_wifi.set_tooltip_text("Scan for networks")
        tools.append(self.scan_wifi)
        content.append(tools)
        self.network_search = Gtk.SearchEntry(placeholder_text="Search networks")
        self.network_search.connect("search-changed", lambda *_args: self.filter_rows("networks", self.network_search.get_text()))
        content.append(self.network_search)
        self.networks = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.networks.add_css_class("boxed-list")
        content.append(self.networks)
        self.wifi_note = label("", "muted", wrap=True)
        content.append(self.wifi_note)
        self.advanced_wifi = button("More settings…", callback=self.open_editor, css="text-button")
        content.append(self.advanced_wifi)

    def build_bluetooth(self):
        content = self.new_page("bluetooth")
        self.bt_row, self.bt_switch = self.radio(content, "Bluetooth", "bt_power")
        hero = Gtk.Box(spacing=12)
        hero.add_css_class("connection-summary")
        hero.append(Gtk.Image(icon_name="bluetooth-symbolic", pixel_size=24))
        description = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
        self.bt_headline = label("Not connected", "summary-title", wrap=True)
        self.bt_description = label("", "summary-subtitle")
        description.append(self.bt_headline)
        description.append(self.bt_description)
        hero.append(description)
        self.scan_bt = button("Add", callback=lambda: self.run_action("bt_scan", {}, "Searching…"), css="quiet-button")
        self.scan_bt.set_valign(Gtk.Align.CENTER)
        self.scan_bt.set_tooltip_text("Find a device")
        hero.append(self.scan_bt)
        content.append(hero)
        tools = Gtk.Box(spacing=8)
        tools.append(label("Devices", "section-label"))
        search = button(icon="system-search-symbolic", callback=lambda: self.reveal_search("bluetooth"), css="header-button")
        search.set_tooltip_text("Search devices · Ctrl+F")
        tools.append(search)
        content.append(tools)
        self.device_search = Gtk.SearchEntry(placeholder_text="Search devices")
        self.device_search.connect("search-changed", lambda *_args: self.filter_rows("devices", self.device_search.get_text()))
        content.append(self.device_search)
        self.devices = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.devices.add_css_class("boxed-list")
        content.append(self.devices)
        self.bt_note = label("", "muted", wrap=True)
        content.append(self.bt_note)
        more = Adw.ExpanderRow(title="More", use_markup=False)
        advanced = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        advanced.add_css_class("boxed-list")
        advanced.append(more)
        content.append(advanced)
        self.bt_option_buttons = []
        for option, title in [("Discoverable", "Make this computer discoverable"), ("Pairable", "Allow incoming pairing")]:
            row = self.action_row(title)
            row.set_tooltip_text("Allow for two minutes")
            allow = button("Allow…", callback=lambda value=option: self.run_action("bt_option", {"option": value, "enabled": True}, "Updating Bluetooth visibility…"), css="quiet-button")
            self.bt_option_buttons.append(allow)
            row.add_suffix(allow)
            more.add_row(row)

    def build_hotspot(self):
        content = self.new_page("hotspot")
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.add_css_class("hero")
        heading = Gtk.Box(spacing=10)
        heading.append(Gtk.Image(icon_name="network-transmit-receive-symbolic", pixel_size=24))
        heading.append(label("Personal hotspot", "hero-label"))
        self.hotspot_badge = label("OFF", "badge")
        self.hotspot_badge.set_hexpand(False)
        self.hotspot_badge.set_ellipsize(Pango.EllipsizeMode.NONE)
        heading.append(self.hotspot_badge)
        self.hotspot_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.hotspot_switch.set_focus_on_click(False)
        self.hotspot_switch.connect("state-set", lambda widget, state: self.radio_request(widget, state, "hotspot_power"))
        heading.append(self.hotspot_switch)
        hero.append(heading)
        self.hotspot_name = label("Personal hotspot", "hero-title", wrap=True)
        self.hotspot_description = label("", "hero-subtitle", wrap=True)
        hero.append(self.hotspot_name)
        hero.append(self.hotspot_description)
        actions = Gtk.Box(spacing=8)
        self.share_button = button("Share QR", callback=self.share, css="suggested-action")
        self.share_button.set_hexpand(True)
        self.edit_hotspot = button("Edit", callback=lambda: self.navigate("hotspot-edit"), css="quiet-button")
        actions.append(self.share_button)
        actions.append(self.edit_hotspot)
        hero.append(actions)
        content.append(hero)
        self.clients_heading = label("Devices", "section-label")
        content.append(self.clients_heading)
        self.clients = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.clients.add_css_class("boxed-list")
        self.clients.add_css_class("device-list")
        content.append(self.clients)
        self.clients_note = label("", "muted", wrap=True)
        content.append(self.clients_note)

    def build_hotspot_editor(self):
        content = self.new_page("hotspot-edit")
        fields = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        fields.add_css_class("boxed-list")
        fields.add_css_class("settings-list")
        content.append(fields)
        self.ssid_entry = Adw.EntryRow(title="Network name", use_markup=False)
        self.password_entry = Adw.PasswordEntryRow(title="New password", use_markup=False)
        self.password_entry.set_tooltip_text("Leave blank to keep the saved password")
        generate = button(icon="view-refresh-symbolic", callback=lambda: self.password_entry.set_text(generate_password()), css="header-button")
        generate.set_tooltip_text("Generate a strong password")
        self.password_entry.add_suffix(generate)
        self.band_row = Adw.ComboRow(title="Band", model=Gtk.StringList.new(["Automatic"]), use_markup=False)
        for field in [self.ssid_entry, self.password_entry, self.band_row]:
            fields.append(field)
        self.ssid_entry.connect("changed", self.mark_dirty)
        self.password_entry.connect("changed", self.mark_dirty)
        self.band_row.connect("notify::selected", self.mark_dirty)
        actions = Gtk.Box(spacing=8)
        self.save_button = button("Save", callback=self.save_hotspot, css="suggested-action")
        self.save_button.set_hexpand(True)
        self.reload_button = button("Cancel", callback=self.cancel_edit, css="quiet-button")
        actions.append(self.save_button)
        actions.append(self.reload_button)
        content.append(actions)
        self.form_note = label("", "muted", wrap=True)
        self.form_note.set_visible(False)
        content.append(self.form_note)

    def build_details(self):
        content = self.new_page("details")
        self.detail_title = label("", "detail-title", wrap=True)
        self.detail_subtitle = label("", "muted", wrap=True)
        content.append(self.detail_title)
        content.append(self.detail_subtitle)
        self.detail_actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.append(self.detail_actions)

    def navigate(self, page):
        if self.updating:
            return
        self.page = page
        self.header_title.set_text({"hotspot": "Hotspot", "hotspot-edit": "Edit hotspot", "details": "Details"}.get(page, "Connections"))
        self.updating = True
        self.tabs["wifi"].set_active(page != "bluetooth" and not (page == "details" and self.detail_target and self.detail_target[0] == "bluetooth"))
        self.tabs["bluetooth"].set_active(not self.tabs["wifi"].get_active())
        self.updating = False
        self.stack.set_visible_child_name(page)
        if self.input_mode == "pointer":
            idle_once(self.reset_open_focus)
        if page == "hotspot":
            self.request_read()

    def go_back(self):
        if self.page == "details":
            self.navigate("hotspot" if self.detail_target[0] == "client" else self.detail_target[0])
        elif self.page == "hotspot-edit":
            self.navigate("hotspot")
        elif self.page == "hotspot":
            self.navigate("wifi")
        else:
            origin = self.origin
            self.close()
            if origin:
                GLib.idle_add(lambda: (panel(True), False)[1])

    def on_key(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            dialog = self.get_visible_dialog()
            if dialog:
                dialog.close()
                return True
            self.go_back()
            return True
        search = keyval in [Gdk.KEY_f, Gdk.KEY_F] and _state & Gdk.ModifierType.CONTROL_MASK
        navigation = keyval in [Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Home, Gdk.KEY_End, Gdk.KEY_Page_Up, Gdk.KEY_Page_Down, Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space]
        if navigation or search:
            self.input_mode = "keyboard"
            self.add_css_class("keyboard-nav")
            self.set_focus_visible(True)
        if search:
            if self.page in ["wifi", "bluetooth"]:
                self.reveal_search(self.page)
                return True
        return False

    def pointer_input(self):
        self.input_mode = "pointer"
        self.remove_css_class("keyboard-nav")
        self.set_focus_visible(False)

    def reset_open_focus(self):
        if self.input_mode == "pointer" and not self.closed and not self.get_visible_dialog():
            self.set_focus_visible(False)
            self.set_focus(None)

    def reveal_search(self, radio):
        entry = self.network_search if radio == "wifi" else self.device_search
        if entry.get_sensitive():
            entry.set_visible(True)
            entry.grab_focus()

    def mark_dirty(self, *_args):
        if not self.updating:
            self.dirty = True
            self.form_note.set_text("Unsaved changes")
            self.form_note.set_visible(True)
            self.edit_hotspot.set_label("Edit •")
            self.update_save_action()
            self.set_controls()

    def reset_form(self):
        self.dirty = False
        self.form_revision = None
        self.render_hotspot(self.data.get("hotspot"))
        self.set_controls()

    def cancel_edit(self):
        self.reset_form()
        self.navigate("hotspot")

    def update_save_action(self):
        state = self.data.get("hotspot") or {}
        self.save_button.set_label("Apply & restart…" if state.get("active") and self.dirty else "Save")

    def radio_request(self, switch, requested, action):
        if self.updating:
            return False
        actual = self.data.get("hotspot", {}).get("active", False) if action == "hotspot_power" and self.data.get("hotspot") else self.data.get("wifi_on" if action == "wifi_power" else "bluetooth_on", False)
        self.updating = True
        switch.set_active(actual)
        switch.set_state(actual)
        self.updating = False
        if requested != actual and not self.busy:
            if action == "hotspot_power":
                self.run_action("hotspot_start" if requested else "hotspot_stop", {}, "Starting hotspot…" if requested else "Stopping hotspot…")
            else:
                self.run_action(action, {"enabled": requested}, "Updating radio…")
        return True

    def run_action(self, action, values, message):
        self.run_job(message, lambda cancel: self.service.perform(action, values, Prompts(self, cancel), cancel))

    def run_job(self, message, function, success=None):
        if self.busy or self.closed:
            return
        self.busy = True
        self.cancel = threading.Event()
        self.progress_text.set_text(message)
        self.progress.set_reveal_child(True)
        self.error.set_reveal_child(False)
        # System authentication dialogs must remain reachable. A fullscreen
        # input catcher or exclusive keyboard grab would block PolicyKit.
        self.backdrop.set_visible(False)
        Layer.set_keyboard_mode(self, Layer.KeyboardMode.ON_DEMAND)
        self.app.hold()
        self.set_controls()

        def worker():
            result = None
            error = None
            try:
                result = function(self.cancel)
            except Exception as exception:
                error = exception

            def finished():
                self.busy = False
                try:
                    if not self.closed:
                        self.progress.set_reveal_child(False)
                        if isinstance(error, Cancelled):
                            self.error.set_reveal_child(False)
                        elif error:
                            self.show_error(str(error))
                        elif success:
                            success(result)
                        self.set_controls()
                        self.request_read()
                        if self.is_active():
                            self.backdrop.present()
                except Exception as exception:
                    if not self.closed:
                        self.show_error(str(exception))
                finally:
                    if self.closed:
                        self.backdrop.destroy()
                        self.destroy()
                    self.app.release()
                return False
            GLib.idle_add(finished, priority=GLib.PRIORITY_DEFAULT)

        threading.Thread(target=worker, daemon=True).start()

    def request_read(self):
        if self.reading or self.closed:
            return False
        self.reading = True

        def worker():
            try:
                data = self.service.read()
                error = None
            except Exception as exception:
                data, error = None, exception

            def ready():
                self.reading = False
                if self.closed:
                    return False
                if error:
                    self.show_error(str(error))
                else:
                    self.data = data
                    self.render()
                    if not self.watched:
                        self.service.watch(self.schedule_read)
                        self.watched = True
                        idle_once(self.reset_open_focus)
                return False
            GLib.idle_add(ready, priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=worker, daemon=True).start()
        return False

    def schedule_read(self):
        if not self.refresh_source and not self.closed:
            self.refresh_source = GLib.timeout_add(250, self.debounced_read)

    def debounced_read(self):
        self.refresh_source = 0
        return self.request_read()

    def poll_clients(self):
        if self.closed:
            return False
        if (self.page == "hotspot" or (self.page == "details" and self.detail_target and self.detail_target[0] == "client")) and not self.busy:
            self.request_read()
        return True

    def show_error(self, message):
        self.error_text.set_text(text(message))
        self.error.set_reveal_child(True)

    def set_controls(self):
        hotspot = self.data.get("hotspot") or {}
        for widget in [self.wifi_switch, self.bt_switch, self.hotspot_switch, self.ssid_entry, self.password_entry, self.band_row, self.save_button, self.reload_button, self.share_button, self.edit_hotspot, self.scan_wifi, self.scan_bt, self.detail_actions, self.advanced_wifi]:
            widget.set_sensitive(not self.busy)
        self.scan_wifi.set_sensitive(not self.busy and self.data.get("wifi_on", False) and not engaged(hotspot))
        self.scan_bt.set_sensitive(not self.busy and self.data.get("bluetooth_on", False))
        transitioning = hotspot.get("phase") in ["starting", "stopping"]
        self.hotspot_switch.set_sensitive(not self.busy and hotspot.get("supported", False) and not transitioning)
        self.wifi_switch.set_sensitive(not self.busy and bool(self.data) and not self.data.get("wifi_error"))
        self.bt_switch.set_sensitive(not self.busy and bool(self.data) and not self.data.get("bluetooth_error"))
        for widget in [self.ssid_entry, self.password_entry, self.band_row]:
            widget.set_sensitive(not self.busy and hotspot.get("supported", False))
        self.save_button.set_sensitive(self.dirty and not self.busy and hotspot.get("supported", False) and not transitioning)
        self.edit_hotspot.set_sensitive(not self.busy and hotspot.get("supported", False))
        self.share_button.set_sensitive(not self.busy and bool(hotspot.get("profile")))
        self.network_search.set_sensitive(self.data.get("wifi_on", False) and not engaged(hotspot))
        self.device_search.set_sensitive(self.data.get("bluetooth_on", False))
        for widget in self.bt_option_buttons:
            widget.set_sensitive(not self.busy and self.data.get("bluetooth_on", False))

    def render(self):
        self.updating = True
        self.wifi_switch.set_active(self.data["wifi_on"])
        self.bt_switch.set_active(self.data["bluetooth_on"])
        hotspot = self.data.get("hotspot")
        sharing = bool(hotspot and engaged(hotspot))
        self.wifi_row.set_subtitle("")
        self.bt_row.set_subtitle("")
        connected = next((item for item in self.data["networks"] if item["connected"]), None)
        phase = (hotspot or {}).get("phase", "")
        self.wifi_headline.set_text("Starting hotspot…" if phase == "starting" else "Stopping hotspot…" if phase == "stopping" else hotspot["ssid"] if sharing else connected["name"] if connected else "Not connected" if self.data["wifi_on"] else "Wi-Fi off")
        clients = self.data.get("clients")
        description = "Hotspot · " + connected_text(len(clients) if clients is not None else None) if sharing else f"Connected · {connected['strength']}%" if connected else ""
        self.wifi_description.set_text(description)
        self.wifi_description.set_visible(bool(description))
        note = self.data["wifi_error"] or ("No networks" if self.data["wifi_on"] and not sharing and not self.data["networks"] else "")
        self.wifi_note.set_text(note)
        self.wifi_note.set_visible(bool(note))
        self.network_tools.set_visible(self.data["wifi_on"] and not sharing)
        self.network_search.set_visible(not sharing and self.show_search(self.network_search, len(self.data["networks"])))
        self.networks.set_visible(not sharing)
        self.update_rows("networks", self.networks, self.data["networks"], lambda entry: (entry["name"], "Connected" if entry["connected"] else "Saved" if entry["profile"] else security_text(entry["security"]), "network-wireless-symbolic"), "wifi")
        self.filter_rows("networks", self.network_search.get_text())
        count = sum(bool(item.get("Connected")) for item in self.data["devices"])
        self.bt_headline.set_text(connected_text(count) if self.data["bluetooth_on"] else "Bluetooth off")
        self.bt_description.set_visible(False)
        note = self.data["bluetooth_error"] or ("No devices" if self.data["bluetooth_on"] and not self.data["devices"] else "")
        self.bt_note.set_text(note)
        self.bt_note.set_visible(bool(note))
        self.device_search.set_visible(self.show_search(self.device_search, len(self.data["devices"])))
        self.update_rows("devices", self.devices, self.data["devices"], lambda entry: (entry["name"], "Connected" if entry.get("Connected") else "Paired" if entry.get("Paired") else "Available", entry.get("Icon") or "bluetooth-symbolic"), "bluetooth")
        self.filter_rows("devices", self.device_search.get_text())
        self.render_hotspot(hotspot)
        self.render_details()
        self.updating = False
        self.set_controls()

    def show_search(self, entry, count):
        focus = self.get_focus()
        return bool(count > 5 or entry.get_text() or (focus and (focus == entry or focus.is_ancestor(entry))))

    def update_rows(self, key, box, entries, describe, radio=None):
        rows = self.row_maps.setdefault(key, {})
        old_order = []
        child = box.get_first_child()
        while child:
            if hasattr(child, "_identity"):
                old_order.append(child._identity)
            child = child.get_next_sibling()
        entries = stable_entries(entries, old_order, key)
        ids = [entry.get("path", entry.get("mac")) for entry in entries]
        for identity in list(rows):
            if identity not in ids:
                box.remove(rows.pop(identity))
        for index, entry in enumerate(entries):
            identity = ids[index]
            title, subtitle, icon = describe(entry)
            if identity not in rows:
                row = self.action_row(title, subtitle, icon)
                if radio:
                    row.set_activatable(True)
                    if key == "clients":
                        row._status_image = Gtk.Image(pixel_size=16)
                        row._status_image.add_css_class("status-icon")
                        row.add_suffix(row._status_image)
                    else:
                        row._status_label = label("", "row-status")
                        row._status_label.set_hexpand(False)
                        row.add_suffix(row._status_label)
                    row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
                    row.connect("activated", lambda _row, value=identity, kind=radio: self.open_details(kind, value))
                rows[identity] = row
                row._identity = identity
                box.insert(row, index)
            row = rows[identity]
            if box.get_row_at_index(index) != row:
                focused = self.get_focus()
                restore = bool(self.input_mode == "keyboard" and focused and focused.is_ancestor(row))
                box.remove(row)
                box.insert(row, index)
                if restore:
                    idle_once(row.grab_focus)
            row.set_title(text(title))
            row.set_subtitle(text(subtitle))
            row._search = title.casefold()
            if key == "clients":
                row._status_image.set_from_icon_name(signal_icon(entry["signal"]))
                row._status_image.set_tooltip_text(f"{entry['signal']} dBm" if entry["signal"] is not None else "Signal unavailable")
            elif radio:
                value = entry.get("battery") if key == "devices" else entry.get("strength")
                row._status_label.set_text(f"{value}%" if value is not None else "")
                row._status_label.set_tooltip_text("Battery" if key == "devices" else "Signal")

    def filter_rows(self, key, search):
        for row in self.row_maps.get(key, {}).values():
            row.set_visible(search.casefold() in row._search)

    def render_hotspot(self, state):
        if not state:
            self.hotspot_description.set_text(self.data.get("wifi_error") or "Unavailable")
            return
        previous_updating = self.updating
        self.updating = True
        self.hotspot_switch.set_active(state["active"])
        phase = state.get("phase", "active" if state["active"] else "inactive")
        self.hotspot_name.set_text(state["ssid"])
        self.hotspot_badge.set_text("LIVE" if state["active"] else phase.upper() if phase != "inactive" else "OFF")
        self.hotspot_badge.set_visible(phase in ["starting", "stopping"])
        clients = self.data.get("clients")
        count = connected_text(len(clients) if clients is not None else None)
        self.hotspot_description.set_text(f"{state['upstream']} · {count}" if state["active"] else "Off")
        self.hotspot_description.set_tooltip_text("Uses mobile or metered data" if state["metered"] or state["upstream"] == "Mobile broadband" else None)
        revision = (state["profile"], state["ssid"], state["band"], tuple(state["bands"]))
        if not self.dirty and not self.busy and revision != self.form_revision:
            self.form_revision = revision
            self.form_profile = state["profile"]
            self.ssid_entry.set_text(state["ssid"])
            self.password_entry.set_text("")
            self.band_ids = list(state["bands"])
            self.band_row.set_model(Gtk.StringList.new([{"": "Automatic", "bg": "2.4 GHz", "a": "5 GHz"}[value] for value in self.band_ids]))
            self.band_row.set_selected(self.band_ids.index(state["band"]) if state["band"] in self.band_ids else 0)
            self.form_note.set_text("")
            self.form_note.set_visible(False)
        self.edit_hotspot.set_label("Edit •" if self.dirty else "Edit")
        self.update_save_action()
        self.clients_heading.set_text("Devices" + (f" · {len(clients)}" if clients else ""))
        self.update_rows("clients", self.clients, clients or [], lambda entry: (client_name(entry), "", None), "client")
        note = "Details unavailable" if clients is None and state["active"] else "No devices" if not clients else ""
        self.clients_note.set_text(note)
        self.clients_note.set_visible(bool(note))
        self.updating = previous_updating

    def save_hotspot(self):
        if not self.capture_form():
            return
        values = self._pending_form
        self._pending_form = None
        def apply(cancel):
            try:
                return self.service.perform("hotspot_save", values, Prompts(self, cancel), cancel)
            finally:
                values["password"] = ""
        self.run_job("Applying hotspot settings…", apply, success=lambda _value: self.saved())

    def capture_form(self):
        state = self.data.get("hotspot") or {}
        if self.form_profile != state.get("profile"):
            self.show_error("The hotspot profile changed while you were editing. Reset the form before applying changes.")
            return False
        expected = {"ssid": self.form_revision[1], "band": self.form_revision[2]} if self.form_revision else None
        self._pending_form = {"ssid": self.ssid_entry.get_text(), "password": self.password_entry.get_text(), "band": self.band_ids[self.band_row.get_selected()], "profile": self.form_profile, "expected": expected}
        return True

    def saved(self):
        self.updating = True
        self.password_entry.set_text("")
        self.updating = False
        self.dirty = False
        self.form_revision = None
        self._pending_form = None
        self.form_note.set_visible(False)
        if self.page == "hotspot-edit":
            self.navigate("hotspot")

    def open_details(self, radio, identity):
        self.detail_target = (radio, identity)
        self.navigate("details")
        self.render_details()

    def render_details(self):
        if not self.detail_target or self.page != "details":
            return
        radio, identity = self.detail_target
        entries = (self.data.get("clients") or []) if radio == "client" else self.data.get("networks" if radio == "wifi" else "devices", [])
        entry = next((item for item in entries if item.get("mac") == identity), None) if radio == "client" else next((item for item in entries if item["path"] == identity), None)
        if entry is None:
            while child := self.detail_actions.get_first_child():
                self.detail_actions.remove(child)
            self.detail_signature = None
            self.client_value_labels.clear()
            self.detail_title.set_text("No longer available")
            self.detail_subtitle.set_text("")
            return
        if radio == "client":
            self.detail_title.set_text(client_name(entry))
            self.detail_subtitle.set_text("")
            self.detail_subtitle.set_visible(False)
            fields = [("IP address", entry.get("ip") or "—"), ("MAC address", entry["mac"]), ("Signal", f"{entry['signal']} dBm" if entry["signal"] is not None else "—"), ("Received", size_text(entry["tx"])), ("Sent", size_text(entry["rx"])), ("Connected", elapsed_text(entry["seconds"]))]
            signature = (radio, identity)
            if signature != self.detail_signature:
                self.detail_signature = signature
                self.client_value_labels.clear()
                while child := self.detail_actions.get_first_child():
                    self.detail_actions.remove(child)
                values = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
                values.add_css_class("boxed-list")
                values.add_css_class("settings-list")
                for title, value in fields:
                    row = self.action_row(title)
                    result = label(value, "row-status")
                    result.set_hexpand(False)
                    result.set_selectable(True)
                    self.client_value_labels[title] = result
                    row.add_suffix(result)
                    if title in ["Received", "Sent"]:
                        row.set_tooltip_text("Since this device connected")
                    values.append(row)
                self.detail_actions.append(values)
            for title, value in fields:
                target = self.client_value_labels[title]
                if target.get_text() != value:
                    target.set_text(value)
            return
        self.detail_title.set_text(entry["name"])
        self.detail_subtitle.set_visible(True)
        if radio == "wifi":
            self.detail_subtitle.set_text(f"{entry['strength']}% · {security_text(entry['security'])}")
            actions = [("Disconnect" if entry["connected"] else "Connect", "wifi_disconnect" if entry["connected"] else "wifi_connect", "suggested-action")]
            if entry["profile"]:
                if entry["security"] in ["wpa-psk", "sae"]:
                    actions.append(("Update password", "wifi_password", "quiet-button"))
                actions.append(("Forget network…", "wifi_forget", "destructive-action"))
        else:
            self.detail_subtitle.set_text("Connected" if entry.get("Connected") else "Paired" if entry.get("Paired") else "Available")
            self.detail_subtitle.set_tooltip_text(entry["Address"])
            actions = [("Disconnect" if entry.get("Connected") else "Connect", "bt_disconnect" if entry.get("Connected") else "bt_connect", "suggested-action")] if entry.get("Paired") else [("Pair device…", "bt_pair", "suggested-action")]
            if entry.get("Paired"):
                actions.extend([("Remove trust" if entry.get("Trusted") else "Trust device…", "bt_trust", "quiet-button"), ("Forget device…", "bt_forget", "destructive-action")])
        signature = (radio, identity, tuple(actions))
        if signature == self.detail_signature:
            return
        self.detail_signature = signature
        focused = self.get_focus()
        restore_focus = bool(self.input_mode == "keyboard" and focused and focused.is_ancestor(self.detail_actions))
        while child := self.detail_actions.get_first_child():
            self.detail_actions.remove(child)
        for title, action, css in actions:
            values = {"path": identity}
            if action == "bt_trust":
                values["enabled"] = not entry.get("Trusted")
            self.detail_actions.append(button(title, callback=lambda kind=action, data=values: self.run_action(kind, data, "Updating connection…"), css=css))
        if radio == "wifi" and not entry["profile"] and entry["security"] in ["enterprise", "wep"]:
            self.detail_actions.append(button("Configure in network editor", callback=self.open_editor, css="quiet-button"))
        if restore_focus and self.detail_actions.get_first_child():
            idle_once(self.detail_actions.get_first_child().grab_focus)

    def share(self):
        generation = self.visibility_generation
        self.run_job("Reading sharing details…", lambda _cancel: self.service.share(), lambda credentials: self.show_share(credentials) if generation == self.visibility_generation else None)

    def open_editor(self):
        executable = shutil.which("nm-connection-editor")
        if not executable:
            self.show_error("nm-connection-editor is not installed. Your saved profiles are unchanged.")
            return
        if self.demo:
            self.show_error("Network editor launch is disabled in the simulation.")
            return
        subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.close()

    def show_share(self, credentials):
        ssid, password = credentials
        dialog = Adw.AlertDialog(heading="Share hotspot")
        dialog.add_response("close", "Done")
        dialog.set_close_response("close")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(label(ssid, "share-name", wrap=True))
        secret = Gtk.PasswordEntry(text=password, editable=False, show_peek_icon=True)
        box.append(secret)
        def copy_password():
            # wl-paste marks this MIME offer as sensitive; Yoru's history
            # watcher will never persist the hotspot password.
            provider = Gdk.ContentProvider.new_union([
                Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", GLib.Bytes.new(password.encode("utf-8"))),
                Gdk.ContentProvider.new_for_bytes("x-kde-passwordManagerHint", GLib.Bytes.new(b"secret")),
            ])
            self.get_clipboard().set_content(provider)
        copy = button("Copy password", callback=copy_password, css="quiet-button")
        copy.set_tooltip_text("Excluded from Yoru clipboard history")
        box.append(copy)
        try:
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(qr_png(ssid, password)))
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_size_request(240, 240)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.add_css_class("qr-code")
            box.prepend(picture)
        except ConnectionError as error:
            box.append(label(str(error), "muted", wrap=True))
        dialog.set_extra_child(box)
        dialog.connect("response", lambda *_args: secret.set_text(""))
        dialog.present(self)

    def on_close(self, *_args):
        if self.closed:
            return False
        self.closed = True
        self.visibility_generation += 1
        # Active NetworkManager sharing is independent of this window's lifetime.
        # Bounded in-flight jobs retain the application until cleanup completes.
        self.service.close()
        if self.poll_source:
            GLib.source_remove(self.poll_source)
            self.poll_source = 0
        if self.refresh_source:
            GLib.source_remove(self.refresh_source)
            self.refresh_source = 0
        self.watched = False
        self.updating = True
        self.password_entry.set_text("")
        self.updating = False
        self.dirty = False
        self.form_revision = None
        if self.busy:
            self.backdrop.set_visible(False)
            self.set_visible(False)
            return True
        self.backdrop.destroy()
        return False

    def resume(self):
        self.closed = False
        self.pointer_input()
        self.visibility_generation += 1
        self.poll_source = GLib.timeout_add_seconds(3, self.poll_clients)
        if not self.busy:
            self.backdrop.present()
        self.present()
        idle_once(self.reset_open_focus)
        self.request_read()


def load_style():
    root = Path(__file__).resolve().parents[3]
    palette = root / "swaync/matugen/colors.css"
    if not palette.exists():
        palette = Path.home() / ".config/swaync/matugen/colors.css"
    provider = Gtk.CssProvider()
    pending = [0]

    def reload_style(*_args):
        pending[0] = 0
        try:
            colors = palette.read_text()
            source = colors + "\n" + Path(__file__).with_name("native.css").read_text()
        except OSError:
            return False
        candidate = Gtk.CssProvider()
        errors = []
        candidate.connect("parsing-error", lambda _provider, _section, error: errors.append(error.message))
        candidate.load_from_string(source)
        if errors:
            return False  # Retain the last good theme during atomic regeneration.
        provider.load_from_string(source)
        match = re.search(r"@define-color\s+surface\s+#([0-9a-fA-F]{6})", colors)
        if match:
            rgb = [int(match[1][index:index + 2], 16) for index in [0, 2, 4]]
            dark = sum(rgb) < 384
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT)
        return False
    reload_style()
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    monitor = Gio.File.new_for_path(str(palette.parent)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
    def changed(_monitor, file, other, _event):
        if file.get_basename() == palette.name or (other and other.get_basename() == palette.name):
            if pending[0]:
                GLib.source_remove(pending[0])
            pending[0] = GLib.timeout_add(150, reload_style)
    monitor.connect("changed", changed)
    return provider, monitor


class Application(Adw.Application):
    def __init__(self, options):
        super().__init__(application_id=None if options.demo else "org.yoru.Connections.Native", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | (Gio.ApplicationFlags.NON_UNIQUE if options.demo else Gio.ApplicationFlags.FLAGS_NONE))
        self.options = options
        self.window = None
        self.resources = None
        self.connect("activate", self.activate_drawer)
        self.connect("command-line", self.command_line)

    def command_line(self, _app, command):
        arguments = command.get_arguments()[1:]
        if "--page" in arguments:
            self.options.page = arguments[arguments.index("--page") + 1]
        elif arguments and arguments[0] in ["wifi", "bluetooth"]:
            self.options.page = arguments[0]
        self.options.from_swaync = "--from-swaync" in arguments
        self.activate()
        return 0

    def activate_drawer(self, *_args):
        if self.window and self.window.closed and self.window.busy:
            self.window.resume()
            self.window.navigate(self.options.page)
            return
        if self.window and not self.window.closed:
            self.window.pointer_input()
            self.window.navigate(self.options.page)
            self.window.present()
            idle_once(self.window.reset_open_focus)
            return
        if not Layer.is_supported():
            raise RuntimeError("The native drawer requires a Wayland layer-shell compositor.")
        if self.resources:
            self.resources[1].cancel()
            Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self.resources[0])
        self.resources = load_style()
        self.window = Drawer(self, DemoService() if self.options.demo else NativeService(), self.options.page, self.options.from_swaync, self.options.demo)
        if self.options.quit_after:
            GLib.timeout_add_seconds(self.options.quit_after, lambda: (self.window.close(), False)[1])
        if self.options.layout_file:
            def dump_layout():
                if self.window.closed or self.window.get_width() <= 1:
                    return False
                data = {"width": self.window.get_width(), "height": self.window.get_height(), "page": self.window.page, "demo": self.options.demo}
                Path(self.options.layout_file).write_text(json.dumps(data))
                return False
            GLib.timeout_add(800, dump_layout)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Native Yoru Connections — ae Orland · https://github.com/ae-orlando")
    parser.add_argument("radio", nargs="?", choices=["wifi", "bluetooth"], default="wifi")
    parser.add_argument("--page", choices=["wifi", "bluetooth", "hotspot"], default=None)
    parser.add_argument("--from-swaync", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--quit-after", type=int, default=0)
    parser.add_argument("--layout-file")
    options = parser.parse_args(argv)
    options.page = options.page or options.radio
    app = Application(options)
    return app.run(["yoru-connections", *(argv if argv is not None else __import__("sys").argv[1:])])


if __name__ == "__main__":
    raise SystemExit(main())
