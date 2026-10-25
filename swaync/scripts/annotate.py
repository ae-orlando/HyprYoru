#!/usr/bin/env python3
"""Choose an image locally, then open it in Swappy.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from pathlib import Path
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk


class Annotate(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.yoru.Annotate", flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        self.hold()
        dialog = Gtk.FileDialog(title="Annotate image")
        images = Gtk.FileFilter(name="Images")
        for mime in ("image/png", "image/jpeg", "image/webp", "image/bmp", "image/tiff"):
            images.add_mime_type(mime)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(images)
        dialog.set_filters(filters)
        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        dialog.set_initial_folder(Gio.File.new_for_path(pictures or str(Path.home())))
        dialog.open(None, None, self.selected)

    def selected(self, dialog, result):
        try:
            selected = dialog.open_finish(result)
            if selected and selected.get_path():
                subprocess.Popen(["swappy", "-f", selected.get_path()], start_new_session=True)
        except GLib.Error:
            pass  # Cancelling the file chooser is not an error.
        finally:
            self.release()
            self.quit()


if __name__ == "__main__":
    raise SystemExit(Annotate().run())
