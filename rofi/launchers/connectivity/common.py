"""Shared connections models, D-Bus calls, and operation guards.

Author: ae. Orland
GitHub: https://github.com/ae-orlando
"""

import fcntl
import os
import stat
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

_interactive = ContextVar("yoru_interactive_authorization", default=False)


@contextmanager
def interactive_authorization():
    """Allow PolicyKit dialogs only inside an explicit user-requested action."""
    token = _interactive.set(True)
    try:
        yield
    finally:
        _interactive.reset(token)


def authorization_flags():
    return (
        Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION
        if _interactive.get()
        else Gio.DBusCallFlags.NONE
    )


class ConnectionError(Exception):
    """A recoverable error that can be presented inside the menu."""


class Cancelled(Exception):
    pass


@dataclass
class Row:
    label: str
    action: str
    target: str = ""
    active: bool = False
    urgent: bool = False
    icon: str = ""


def text(value):
    """Keep arbitrary SSIDs/device names literal and within a single row."""
    return "".join(char if char.isprintable() else " " for char in str(value))


def call(bus, service, path, interface, method, signature=None, args=(), timeout=5000):
    try:
        protected = method in [
            "GetSecrets",
            "Set",
            "Update",
            "AddConnection",
            "AddAndActivateConnection",
            "ActivateConnection",
            "DeactivateConnection",
            "Delete",
            "CheckpointCreate",
            "CheckpointAdjustRollbackTimeout",
            "CheckpointRollback",
            "CheckpointDestroy",
        ]
        deadline = max(timeout, 120000) if _interactive.get() and protected else timeout
        result = bus.call_sync(
            service,
            path,
            interface,
            method,
            GLib.Variant(signature, args) if signature else None,
            None,
            authorization_flags(),
            deadline,
            None,
        )
        return result
    except GLib.Error as error:
        raise ConnectionError(error.message.split(": ", 1)[-1]) from error


def props(bus, service, path, interface):
    return call(
        bus,
        service,
        path,
        "org.freedesktop.DBus.Properties",
        "GetAll",
        "(s)",
        (interface,),
    ).unpack()[0]


def set_prop(bus, service, path, interface, name, kind, value):
    call(
        bus,
        service,
        path,
        "org.freedesktop.DBus.Properties",
        "Set",
        "(ssv)",
        (interface, name, GLib.Variant(kind, value)),
    )


def panel(visible):
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        call(
            bus,
            "org.erikreider.swaync.cc",
            "/org/erikreider/swaync/cc",
            "org.erikreider.swaync.cc",
            "SetVisibility",
            "(b)",
            (visible,),
        )
    except (GLib.Error, ConnectionError):
        pass


def panel_visible():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return call(
            bus,
            "org.erikreider.swaync.cc",
            "/org/erikreider/swaync/cc",
            "org.erikreider.swaync.cc",
            "GetVisibility",
        ).unpack()[0]
    except (GLib.Error, ConnectionError):
        return False


def notify(message, notification_id=0, timeout=5000):
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return call(
            bus,
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "Notify",
            "(susssasa{sv}i)",
            (
                "Yoru Connections",
                notification_id,
                "network-wireless",
                "Yoru Connections",
                text(message),
                [],
                {},
                timeout,
            ),
        ).unpack()[0]
    except (GLib.Error, ConnectionError):
        return 0


def close_notice(notification_id):
    if not notification_id:
        return
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        call(
            bus,
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "CloseNotification",
            "(u)",
            (notification_id,),
        )
    except (GLib.Error, ConnectionError):
        pass


@contextmanager
def private_context():
    """Keep backend async callbacks off the native GTK main context."""
    context = GLib.MainContext.new()
    context.push_thread_default()
    try:
        yield context
    finally:
        context.pop_thread_default()


@contextmanager
def operation_lock(radio):
    """Serialize explicit requests across Rofi and SwayNC, without a daemon."""
    root = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/yoru-{os.getuid()}"))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root_info = root.lstat()
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or root_info.st_uid != os.getuid()
        or root_info.st_mode & 0o077
    ):
        raise ConnectionError("Unsafe user runtime directory.")
    directory = root / "yoru-connections"
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise ConnectionError("Unsafe connections runtime directory.")
    descriptor = os.open(
        directory / f"{radio}.lock",
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ConnectionError(
                        "Another radio operation is still running. Try again shortly."
                    )
                time.sleep(0.05)
        yield
    finally:
        os.close(descriptor)


def wait_for(predicate, cancel=None, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if predicate():
            return
        time.sleep(0.1)
    raise ConnectionError(
        "The operation timed out. Your saved connections have been preserved."
    )
