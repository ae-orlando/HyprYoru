"""Palette-driven Rofi presentation; labels never become command arguments.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import html
import json
from pathlib import Path
import subprocess
import threading

from common import Cancelled, ConnectionError, Row, text


class Menu:
    def __init__(self):
        self.theme = Path(__file__).resolve().parents[2] / "styles/connectivity.rasi"
        self.positions = {}
        self.placement = []
        # Rofi already respects Waybar's exclusive zone; add only our margin.
        try:
            result = subprocess.run(["hyprctl", "-j", "monitors"], capture_output=True, text=True, timeout=2, check=True)
            monitor = next(item for item in json.loads(result.stdout) if item["focused"])
            self.placement = ["-m", monitor["name"]]
        except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
            pass

    def command(self, title, message):
        # Explicit Pango-sized lines avoid Rofi underestimating wrapped message
        # heights when the status font differs from the row font.
        import gi
        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Pango, PangoCairo
        layout = Pango.Layout.new(PangoCairo.FontMap.get_default().create_context())
        layout.set_font_description(Pango.FontDescription.from_string("Adwaita Sans 10"))
        layout.set_width(350 * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        value = text(message)
        layout.set_text(value, -1)
        encoded = value.encode("utf-8")
        wrapped = "\n".join(encoded[line.start_index:line.start_index + line.length].decode("utf-8").rstrip() for line in layout.get_lines_readonly())
        return ["rofi", "-dmenu", "-i", "-no-custom", "-no-sort", "-show-icons", "-theme", str(self.theme), "-p", text(title), "-mesg", html.escape(wrapped), *self.placement]

    def choose(self, title, message, rows, key=None, timeout=None):
        if not rows:
            rows = [Row("Back", "back")]
        key = key or title
        selected, search = self.positions.get(key, (0, ""))
        command = [*self.command(title, message), "-format", "i\x1ff", "-filter", search]
        # Do not restore an unfiltered index over a preloaded filter: Rofi can
        # otherwise return a hidden row instead of the visible matching entry.
        if not search:
            command += ["-selected-row", str(min(selected, len(rows) - 1))]
        if key.startswith("details") or key in ["confirmation", "advanced", "error"]:
            command += ["-theme-str", "entry { enabled: false; }"]
        for flag, indices in [("-a", [str(i) for i, row in enumerate(rows) if row.active]), ("-u", [str(i) for i, row in enumerate(rows) if row.urgent])]:
            if indices:
                command += [flag, ",".join(indices)]
        lines = []
        for row in rows:
            metadata = ["icon", row.icon] if row.icon else []
            if row.action in ["scan", "power_on", "power_off", "advanced", "exit", "back", "cancel"]:
                metadata += ["permanent", "true"]
            lines.append(text(row.label) + ("\0" + "\x1f".join(metadata) if metadata else ""))
        data = "\n".join(lines) + "\n"
        try:
            result = subprocess.run(command, input=data, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise Cancelled() from error
        if result.returncode == 1:
            raise Cancelled()
        if result.returncode:
            raise ConnectionError("Rofi could not display the connections menu.")
        index, _, search = result.stdout.rstrip("\n").partition("\x1f")
        try:
            index = int(index)
            if not 0 <= index < len(rows):
                raise ValueError()
        except ValueError as error:
            raise ConnectionError("Invalid menu selection.") from error
        self.positions[key] = (index, search)
        return rows[index]

    def confirm(self, title, message, timeout=None):
        try:
            return self.choose(title, message, [Row("Cancel", "cancel", icon="dialog-cancel"), Row("Confirm", "confirm", urgent=True, icon="dialog-warning")], key="confirmation", timeout=timeout).action == "confirm"
        except Cancelled:
            return False
        finally:
            self.positions.pop("confirmation", None)

    def password(self, title, message, numeric=False, timeout=None):
        command = [item for item in self.command(title, message) if item != "-no-custom"]
        command += ["-password", "-theme-str", 'listview { enabled: false; } entry { placeholder: "Enter secret…"; }']
        try:
            result = subprocess.run(command, input="", capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise Cancelled() from error
        if result.returncode == 1:
            raise Cancelled()
        if result.returncode:
            raise ConnectionError("The password dialog could not be opened.")
        value = result.stdout.rstrip("\n")
        if not value:
            raise Cancelled()
        if numeric and (not value.isascii() or not value.isdigit() or len(value) > 6):
            raise ConnectionError("A Bluetooth passkey must contain at most six digits.")
        return value

    def work(self, title, function):
        """A bounded operation with an owned progress window and cancellation."""
        cancel = threading.Event()
        done = threading.Event()
        outcome = []

        def worker():
            try:
                outcome.append((True, function(cancel)))
            except Exception as error:
                outcome.append((False, error))
            finally:
                done.set()

        command = [*self.command(title, "Working…  ·  Esc cancels the request"), "-format", "i", "-theme-str", "entry { enabled: false; }"]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        process.stdin.write("Cancel\0permanent\x1ftrue\n")
        process.stdin.close()
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            while not done.wait(0.05):
                if process.poll() is not None:
                    cancel.set()
            if process.poll() is None:
                process.terminate()  # This exact Rofi process belongs to this operation.
            process.wait(timeout=3)
            success, value = outcome[0]
            if not success:
                raise value
            if cancel.is_set():
                raise Cancelled()
            return value
        finally:
            cancel.set()
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=3)
            process.stdout.close()
            process.stderr.close()
