#!/usr/bin/env python3
"""Validate local Waybar selection without starting a real desktop bar.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).parents[1]
HEADER = "#!/usr/bin/env bash\n# Author: ae Orland\n# GitHub: https://github.com/ae-orlando\n"


class StartupTests(unittest.TestCase):
    def test_private_build_receives_the_original_arguments(self):
        with tempfile.TemporaryDirectory(prefix="waybar-start-", dir="/tmp/opencode") as directory:
            root = Path(directory)
            executable = root / "yoru/waybar/waybar"
            executable.parent.mkdir(parents=True)
            executable.write_text(HEADER + 'printf "%s\\n" "$@"\n')
            executable.chmod(0o755)
            env = os.environ | {"XDG_DATA_HOME": str(root)}
            result = subprocess.run(["bash", str(SCRIPTS / "start-waybar.sh"), "--version", "argument with spaces"],
                                    env=env, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines(), ["--version", "argument with spaces"])

    @unittest.skipUnless(Path("/usr/bin/waybar").is_file(), "Distro Waybar is not installed")
    def test_missing_private_build_falls_back_to_distro_version_only(self):
        with tempfile.TemporaryDirectory(prefix="waybar-start-", dir="/tmp/opencode") as directory:
            env = os.environ | {"XDG_DATA_HOME": directory}
            result = subprocess.run(["bash", str(SCRIPTS / "start-waybar.sh"), "--version"],
                                    env=env, capture_output=True, text=True, check=True)
            self.assertTrue(result.stdout.startswith("Waybar v"))

    def test_reload_helper_starts_its_sibling_launcher_if_bar_is_stopped(self):
        with tempfile.TemporaryDirectory(prefix="waybar-start-", dir="/tmp/opencode") as directory:
            root = Path(directory)
            log = root / "calls"
            shutil.copy2(SCRIPTS / "launch.sh", root / "launch.sh")
            for name, text in {
                "pgrep": "exit 1\n",
                "start-waybar.sh": 'printf "launcher selected\\n" >> "$TEST_LOG"\n',
                "swaync-client": 'printf "unexpected notification call\\n" >> "$TEST_LOG"\n',
            }.items():
                path = root / name
                path.write_text(HEADER + text)
                path.chmod(0o755)
            env = os.environ | {"PATH": str(root) + ":" + os.environ["PATH"], "TEST_LOG": str(log)}
            # The launcher is asynchronous, but a FIFO is unnecessary: communicate
            # waits for the test shell below to reap its own short-lived child.
            subprocess.run(["bash", "-c", 'source "$1"; wait', "test", str(root / "launch.sh")],
                           env=env, capture_output=True, text=True, check=True)
            self.assertEqual(log.read_text(), "launcher selected\n")


if __name__ == "__main__":
    unittest.main()
