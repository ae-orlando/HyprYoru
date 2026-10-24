#!/usr/bin/env python
"""Compatibility launcher: native drawer by default, explicit Rofi fallback.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import sys


def fallback(args):
    if "--demo" in args:
        print("The native preview requires GTK4 and Wayland layer-shell support.", file=sys.stderr)
        return 1
    if "--page" in args and args[args.index("--page") + 1] == "hotspot":
        from common import notify
        notify("Native GTK4/layer-shell support is unavailable. Manage the hotspot in the network editor; no connection was changed.")
        return 0
    if "--page" in args:
        index = args.index("--page")
        page = args[index + 1]
        args = [*args[:index], *args[index + 2:]]
        if args and page in ["wifi", "bluetooth"]:
            args[0] = page
    from menu import main as legacy
    return legacy(args)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--legacy" in args or any(flag in args for flag in ["--state", "--status", "--power"]):
        args = [arg for arg in args if arg != "--legacy"]
        from menu import main as legacy
        return legacy(args)
    try:
        from ctypes import CDLL
        from ctypes.util import find_library
        CDLL(find_library("gtk4-layer-shell") or "libgtk4-layer-shell.so")
        import gi
        for namespace, version in [("Gtk", "4.0"), ("Adw", "1"), ("Gtk4LayerShell", "1.0")]:
            gi.require_version(namespace, version)
        from drawer import Gtk, Layer, main as native
        Gtk.init()
        if not Layer.is_supported():
            return fallback(args)
    except (ImportError, ValueError, OSError):
        return fallback(args)
    return native(args)


if __name__ == "__main__":
    raise SystemExit(main())
