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
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Gtk4LayerShell as Layer, Pango

from common import Cancelled, ConnectionError, panel, text
from hotspot import engaged, generate_password, qr_png
from native_service import DemoService, NativeService, stable_entries


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
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, spacing=2)
        titles.append(label("YORU  /  CONNECTIVITY", "eyebrow"))
        titles.append(label("Connections", "drawer-title"))
        header.append(titles)
        if demo:
            header.append(label("PREVIEW", "badge"))
        header.append(button(icon="window-close-symbolic", callback=self.close, css="header-button"))
        shell.append(header)

        tabs = Gtk.Box(spacing=6, homogeneous=True)
        tabs.add_css_class("page-tabs")
        self.tabs = {}
        for name, title in [("wifi", "Wi-Fi"), ("bluetooth", "Bluetooth")]:
            tab = Gtk.ToggleButton(label=title, hexpand=True)
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
        self.build_details()
        self.set_controls()
        self.navigate(page)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)
        self.connect("close-request", self.on_close)
        self.poll_source = GLib.timeout_add_seconds(3, self.poll_clients)
        self.backdrop.present()
        self.present()
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
        if icon:
            image = Gtk.Image(icon_name=icon, pixel_size=20)
            image.add_css_class("row-icon")
            row.add_prefix(image)
        return row

    def radio(self, content, title, action):
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        icons = {"wifi_power": "network-wireless-symbolic", "bt_power": "bluetooth-symbolic", "hotspot_power": "network-transmit-receive-symbolic"}
        row = self.action_row(title, "Checking adapter…", icons[action])
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        switch.connect("state-set", lambda widget, state: self.radio_request(widget, state, action))
        row.add_suffix(switch)
        box.append(row)
        content.append(box)
        return row, switch

    def build_wifi(self):
        content = self.new_page("wifi")
        self.wifi_row, self.wifi_switch = self.radio(content, "Wi-Fi", "wifi_power")
        self.wifi_hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.wifi_hero.add_css_class("hero")
        self.wifi_hero.append(label("YOUR CONNECTION", "hero-eyebrow"))
        self.wifi_headline = label("Finding your connection…", "hero-title", wrap=True)
        self.wifi_description = label("Live system state. No scan is started automatically.", "hero-subtitle", wrap=True)
        self.wifi_hero.append(self.wifi_headline)
        self.wifi_hero.append(self.wifi_description)
        self.manage_hotspot = button("Hotspot settings  →", callback=lambda: self.navigate("hotspot"), css="hero-button")
        self.wifi_hero.append(self.manage_hotspot)
        content.append(self.wifi_hero)
        tools = Gtk.Box(spacing=8)
        tools.append(label("NEARBY NETWORKS", "section-label"))
        self.scan_wifi = button(icon="view-refresh-symbolic", callback=lambda: self.run_action("wifi_scan", {}, "Refreshing nearby networks…"), css="header-button")
        self.scan_wifi.set_tooltip_text("Scan for networks")
        tools.append(self.scan_wifi)
        content.append(tools)
        self.network_search = Gtk.SearchEntry(placeholder_text="Search saved and nearby networks")
        self.network_search.connect("search-changed", lambda *_args: self.filter_rows("networks", self.network_search.get_text()))
        content.append(self.network_search)
        self.networks = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.networks.add_css_class("boxed-list")
        content.append(self.networks)
        self.wifi_note = label("", "muted", wrap=True)
        content.append(self.wifi_note)
        self.advanced_wifi = button("Advanced network settings", callback=self.open_editor, css="quiet-button")
        content.append(self.advanced_wifi)

    def build_bluetooth(self):
        content = self.new_page("bluetooth")
        self.bt_row, self.bt_switch = self.radio(content, "Bluetooth", "bt_power")
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.add_css_class("hero")
        hero.append(label("YOUR DEVICES", "hero-eyebrow"))
        self.bt_headline = label("Ready when you are", "hero-title")
        hero.append(self.bt_headline)
        hero.append(label("Connected devices first. Nearby discovery stays off until you ask.", "hero-subtitle", wrap=True))
        self.scan_bt = button("Find a device", callback=lambda: self.run_action("bt_scan", {}, "Looking for Bluetooth devices…"), css="hero-button")
        hero.append(self.scan_bt)
        content.append(hero)
        content.append(label("PAIRED & AVAILABLE", "section-label"))
        self.device_search = Gtk.SearchEntry(placeholder_text="Search devices")
        self.device_search.connect("search-changed", lambda *_args: self.filter_rows("devices", self.device_search.get_text()))
        content.append(self.device_search)
        self.devices = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.devices.add_css_class("boxed-list")
        content.append(self.devices)
        self.bt_note = label("", "muted", wrap=True)
        content.append(self.bt_note)
        advanced = self.section(content, "NEARBY VISIBILITY")
        self.bt_option_buttons = []
        for option, title in [("Discoverable", "Make this computer discoverable"), ("Pairable", "Allow incoming pairing")]:
            row = self.action_row(title, "Two-minute window; never enabled automatically")
            allow = button("Allow…", callback=lambda value=option: self.run_action("bt_option", {"option": value, "enabled": True}, "Updating Bluetooth visibility…"), css="quiet-button")
            self.bt_option_buttons.append(allow)
            row.add_suffix(allow)
            advanced.append(row)

    def build_hotspot(self):
        content = self.new_page("hotspot")
        self.hotspot_row, self.hotspot_switch = self.radio(content, "Personal hotspot", "hotspot_power")
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.add_css_class("hero")
        heading = Gtk.Box(spacing=10)
        heading.append(Gtk.Image(icon_name="network-transmit-receive-symbolic", pixel_size=30))
        heading.append(label("SHARE YOUR CONNECTION", "hero-eyebrow"))
        self.hotspot_badge = label("OFF", "badge")
        self.hotspot_badge.set_hexpand(False)
        self.hotspot_badge.set_ellipsize(Pango.EllipsizeMode.NONE)
        heading.append(self.hotspot_badge)
        hero.append(heading)
        self.hotspot_name = label("Personal hotspot", "hero-title", wrap=True)
        self.hotspot_description = label("", "hero-subtitle", wrap=True)
        hero.append(self.hotspot_name)
        hero.append(self.hotspot_description)
        self.share_button = button("Share password / QR", callback=self.share, css="hero-button")
        hero.append(self.share_button)
        content.append(hero)
        self.upstream_note = label("", "info-note", wrap=True)
        content.append(self.upstream_note)
        fields = self.section(content, "HOTSPOT SETTINGS")
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
        self.save_button = button("Save settings", callback=self.save_hotspot, css="suggested-action")
        self.save_button.set_hexpand(True)
        self.reload_button = button("Reset", callback=self.reset_form, css="quiet-button")
        actions.append(self.save_button)
        actions.append(self.reload_button)
        content.append(actions)
        self.form_note = label("Changes are staged until you apply them. Hotspots do not start automatically at login.", "muted", wrap=True)
        content.append(self.form_note)
        self.clients_heading = label("CONNECTED DEVICES", "section-label")
        content.append(self.clients_heading)
        self.clients = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.clients.add_css_class("boxed-list")
        content.append(self.clients)
        self.clients_note = label("", "muted", wrap=True)
        content.append(self.clients_note)

    def build_details(self):
        content = self.new_page("details")
        self.detail_kind = label("CONNECTION DETAILS", "section-label")
        self.detail_title = label("", "detail-title", wrap=True)
        self.detail_subtitle = label("", "muted", wrap=True)
        content.append(self.detail_kind)
        content.append(self.detail_title)
        content.append(self.detail_subtitle)
        self.detail_actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.append(self.detail_actions)

    def navigate(self, page):
        if self.updating:
            return
        self.page = page
        self.updating = True
        self.tabs["wifi"].set_active(page != "bluetooth" and not (page == "details" and self.detail_target and self.detail_target[0] == "bluetooth"))
        self.tabs["bluetooth"].set_active(not self.tabs["wifi"].get_active())
        self.updating = False
        self.stack.set_visible_child_name(page)
        if page == "hotspot":
            self.request_read()

    def go_back(self):
        if self.page == "details":
            self.navigate(self.detail_target[0])
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
        return False

    def mark_dirty(self, *_args):
        if not self.updating:
            self.dirty = True
            self.form_note.set_text("Unsaved changes · applying to a running hotspot requires a restart confirmation.")

    def reset_form(self):
        self.dirty = False
        self.form_revision = None
        self.render_hotspot(self.data.get("hotspot"))

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
                            self.show_error("Request cancelled. Saved connections were kept.")
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
        if self.page == "hotspot" and not self.busy:
            self.request_read()
        return True

    def show_error(self, message):
        self.error_text.set_text(text(message))
        self.error.set_reveal_child(True)

    def set_controls(self):
        hotspot = self.data.get("hotspot") or {}
        for widget in [self.wifi_switch, self.bt_switch, self.hotspot_switch, self.ssid_entry, self.password_entry, self.band_row, self.save_button, self.reload_button, self.share_button, self.scan_wifi, self.scan_bt, self.detail_actions, self.advanced_wifi]:
            widget.set_sensitive(not self.busy)
        self.scan_wifi.set_sensitive(not self.busy and self.data.get("wifi_on", False) and not engaged(hotspot))
        self.scan_bt.set_sensitive(not self.busy and self.data.get("bluetooth_on", False))
        transitioning = hotspot.get("phase") in ["starting", "stopping"]
        self.hotspot_switch.set_sensitive(not self.busy and hotspot.get("supported", False) and not transitioning)
        self.wifi_switch.set_sensitive(not self.busy and bool(self.data) and not self.data.get("wifi_error"))
        self.bt_switch.set_sensitive(not self.busy and bool(self.data) and not self.data.get("bluetooth_error"))
        for widget in [self.ssid_entry, self.password_entry, self.band_row]:
            widget.set_sensitive(not self.busy and hotspot.get("supported", False))
        self.save_button.set_sensitive(not self.busy and hotspot.get("supported", False) and not transitioning)
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
        self.wifi_row.set_subtitle("Hotspot mode · radio on" if sharing else "Radio on" if self.data["wifi_on"] else self.data["wifi_error"] or "Radio off")
        self.bt_row.set_subtitle("Radio on" if self.data["bluetooth_on"] else self.data["bluetooth_error"] or "Radio off")
        connected = next((item for item in self.data["networks"] if item["connected"]), None)
        phase = (hotspot or {}).get("phase", "")
        self.wifi_headline.set_text("Starting your hotspot…" if phase == "starting" else "Stopping sharing…" if phase == "stopping" else "You're sharing a connection" if sharing else connected["name"] if connected else "Ready to connect" if self.data["wifi_on"] else "A little offline time")
        self.wifi_description.set_text(f"{hotspot['ssid']} · {hotspot['upstream']}" if sharing else f"{connected['strength']}% signal · saved profile" if connected else "Choose a saved or nearby network. Scanning only starts when you request it.")
        self.wifi_note.set_text("The hotspot is using this adapter. Stop sharing in Hotspot settings before joining another network." if sharing else self.data["wifi_error"] or ("Turn Wi-Fi on to browse nearby networks." if not self.data["wifi_on"] else "No cached networks. Use Refresh to scan." if not self.data["networks"] else "Connected and saved networks are shown first."))
        self.network_search.set_visible(not sharing)
        self.networks.set_visible(not sharing)
        self.update_rows("networks", self.networks, self.data["networks"], lambda entry: (entry["name"], f"{entry['strength']}% signal · " + ("Connected" if entry["connected"] else "Saved" if entry["profile"] else entry["security"]), "network-wireless-symbolic"), "wifi")
        self.filter_rows("networks", self.network_search.get_text())
        count = sum(bool(item.get("Connected")) for item in self.data["devices"])
        self.bt_headline.set_text(f"{count} device(s) connected" if count else "Make a connection")
        self.bt_note.set_text(self.data["bluetooth_error"] or ("Turn Bluetooth on to browse devices." if not self.data["bluetooth_on"] else "No cached devices. Find a device starts a bounded discovery session." if not self.data["devices"] else "Pairing and trust always require your explicit choice."))
        self.update_rows("devices", self.devices, self.data["devices"], lambda entry: (entry["name"], ("Connected" if entry.get("Connected") else "Paired" if entry.get("Paired") else "Not paired") + (f" · {entry['battery']}% battery" if entry["battery"] is not None else ""), entry.get("Icon") or "bluetooth-symbolic"), "bluetooth")
        self.filter_rows("devices", self.device_search.get_text())
        self.render_hotspot(hotspot)
        self.render_details()
        self.updating = False
        self.set_controls()

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
                    row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
                    row.connect("activated", lambda _row, value=identity, kind=radio: self.open_details(kind, value))
                rows[identity] = row
                row._identity = identity
                box.insert(row, index)
            row = rows[identity]
            if box.get_row_at_index(index) != row:
                focused = self.get_focus()
                restore = bool(focused and focused.is_ancestor(row))
                box.remove(row)
                box.insert(row, index)
                if restore:
                    idle_once(row.grab_focus)
            row.set_title(text(title))
            row.set_subtitle(text(subtitle))
            row._search = title.casefold()

    def filter_rows(self, key, search):
        for row in self.row_maps.get(key, {}).values():
            row.set_visible(search.casefold() in row._search)

    def render_hotspot(self, state):
        if not state:
            self.hotspot_description.set_text(self.data.get("wifi_error") or "No compatible Wi-Fi adapter is available.")
            return
        previous_updating = self.updating
        self.updating = True
        self.hotspot_switch.set_active(state["active"])
        phase = state.get("phase", "active" if state["active"] else "inactive")
        self.hotspot_row.set_subtitle("Starting sharing…" if phase == "starting" else "Stopping sharing…" if phase == "stopping" else "Sharing is active" if state["active"] else "Saved profile ready" if state["profile"] else "Create a protected hotspot")
        self.hotspot_name.set_text(state["ssid"])
        self.hotspot_badge.set_text("LIVE" if state["active"] else phase.upper() if phase != "inactive" else "OFF")
        clients = self.data.get("clients")
        count = "Client details unavailable" if clients is None else f"{len(clients)} connected device(s)"
        self.hotspot_description.set_text(count if state["active"] else "A private connection, ready when you need it.")
        note = ("Sharing via " if state["shared"] else "Upstream: ") + state["upstream"]
        if state["metered"] or state["upstream"] == "Mobile broadband":
            note += " · Mobile or metered data may be used."
        self.upstream_note.set_text(note)
        revision = (state["profile"], state["ssid"], state["band"], tuple(state["bands"]))
        if not self.dirty and not self.busy and revision != self.form_revision:
            self.form_revision = revision
            self.form_profile = state["profile"]
            self.ssid_entry.set_text(state["ssid"])
            self.password_entry.set_text("")
            self.band_ids = list(state["bands"])
            self.band_row.set_model(Gtk.StringList.new([{"": "Automatic", "bg": "2.4 GHz", "a": "5 GHz"}[value] for value in self.band_ids]))
            self.band_row.set_selected(self.band_ids.index(state["band"]) if state["band"] in self.band_ids else 0)
            self.form_note.set_text("Changes are staged until you apply them. Closing this drawer does not stop an active hotspot.")
        self.save_button.set_label("Apply & restart…" if state["active"] else "Save settings")
        self.clients_heading.set_text("CONNECTED DEVICES" + (f"  /  {len(clients)}" if clients is not None else ""))
        self.update_rows("clients", self.clients, clients or [], lambda entry: (entry["name"], " · ".join(filter(None, [entry.get("ip"), entry["mac"], f"{entry['signal']} dBm" if entry["signal"] is not None else "", size_text(entry["rx"] + entry["tx"])])), "network-workgroup-symbolic"))
        self.clients_note.set_text("Traffic shown is per device since it connected—not a billing meter." if clients else "Client statistics are unavailable." if clients is None and state["active"] else "No devices are connected.")
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

    def open_details(self, radio, identity):
        self.detail_target = (radio, identity)
        self.navigate("details")
        self.render_details()

    def render_details(self):
        if not self.detail_target or self.page != "details":
            return
        radio, identity = self.detail_target
        entries = self.data.get("networks" if radio == "wifi" else "devices", [])
        entry = next((item for item in entries if item["path"] == identity), None)
        if entry is None:
            while child := self.detail_actions.get_first_child():
                self.detail_actions.remove(child)
            self.detail_signature = None
            self.detail_title.set_text("No longer available")
            self.detail_subtitle.set_text("Go back and refresh the list.")
            return
        self.detail_title.set_text(entry["name"])
        self.detail_kind.set_text("WI-FI NETWORK" if radio == "wifi" else "BLUETOOTH DEVICE")
        if radio == "wifi":
            self.detail_subtitle.set_text(f"{entry['strength']}% signal · {entry['security']} · " + ("Saved profile" if entry["profile"] else "Not saved"))
            actions = [("Disconnect" if entry["connected"] else "Connect", "wifi_disconnect" if entry["connected"] else "wifi_connect", "suggested-action")]
            if entry["profile"]:
                if entry["security"] in ["wpa-psk", "sae"]:
                    actions.append(("Update saved password", "wifi_password", "quiet-button"))
                actions.append(("Forget network…", "wifi_forget", "destructive-action"))
        else:
            self.detail_subtitle.set_text(("Connected" if entry.get("Connected") else "Paired" if entry.get("Paired") else "Not paired") + " · " + entry["Address"])
            actions = [("Disconnect" if entry.get("Connected") else "Connect", "bt_disconnect" if entry.get("Connected") else "bt_connect", "suggested-action")] if entry.get("Paired") else [("Pair device…", "bt_pair", "suggested-action")]
            if entry.get("Paired"):
                actions.extend([("Remove trust" if entry.get("Trusted") else "Trust device…", "bt_trust", "quiet-button"), ("Forget device…", "bt_forget", "destructive-action")])
        signature = (radio, identity, tuple(actions))
        if signature == self.detail_signature:
            return
        self.detail_signature = signature
        focused = self.get_focus()
        restore_focus = bool(focused and focused.is_ancestor(self.detail_actions))
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
        dialog = Adw.AlertDialog(heading="Share your hotspot", body="Only show this code to people you trust. Clipboard history may retain copied passwords.")
        dialog.add_response("close", "Done")
        dialog.set_close_response("close")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(label(ssid, "share-name", wrap=True))
        secret = Gtk.PasswordEntry(text=password, editable=False, show_peek_icon=True)
        box.append(secret)
        def copy_password():
            value = GObject.Value()
            value.init(GObject.TYPE_STRING)
            value.set_string(password)
            self.get_clipboard().set(value)
        box.append(button("Copy password", callback=copy_password, css="quiet-button"))
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
        if self.busy:
            self.backdrop.set_visible(False)
            self.set_visible(False)
            return True
        self.backdrop.destroy()
        return False

    def resume(self):
        self.closed = False
        self.visibility_generation += 1
        self.poll_source = GLib.timeout_add_seconds(3, self.poll_clients)
        if not self.busy:
            self.backdrop.present()
        self.present()
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
            self.window.navigate(self.options.page)
            self.window.present()
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
