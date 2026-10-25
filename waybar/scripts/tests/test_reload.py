#!/usr/bin/env python3
"""Check SUPER+R with mocked processes; never signal a real bar or daemon.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ReloadTests(unittest.TestCase):
    def test_running_services_are_only_reloaded(self):
        with tempfile.TemporaryDirectory(prefix="waybar-reload-", dir="/tmp/opencode") as directory:
            root = Path(directory)
            log = root / "calls"
            scripts = {
                "pgrep": 'exit 0\n',
                "pkill": 'printf "pkill %s\\n" "$*" >> "$TEST_LOG"\n',
                "swaync-client": 'printf "swaync-client %s\\n" "$*" >> "$TEST_LOG"\n',
                "waybar": 'printf "unexpected restart\\n" >> "$TEST_LOG"\n',
            }
            for name, text in scripts.items():
                path = root / name
                path.write_text("#!/usr/bin/env bash\n" + text)
                path.chmod(0o755)
            env = os.environ | {"PATH": str(root) + ":" + os.environ["PATH"], "TEST_LOG": str(log)}
            subprocess.run(["bash", str(Path(__file__).parents[1] / "launch.sh")], env=env, check=True)
            self.assertEqual(log.read_text().splitlines(),
                             [f"pkill -u {os.getuid()} -SIGUSR2 -x waybar", "swaync-client -rs"])

    def test_an_intentionally_stopped_notification_daemon_stays_stopped(self):
        with tempfile.TemporaryDirectory(prefix="waybar-reload-", dir="/tmp/opencode") as directory:
            root = Path(directory)
            log = root / "calls"
            scripts = {
                "pgrep": '[[ "${@: -1}" == "waybar" ]]\n',
                "pkill": 'printf "bar reload\\n" >> "$TEST_LOG"\n',
                "swaync-client": 'printf "unexpected notification call\\n" >> "$TEST_LOG"\n',
            }
            for name, text in scripts.items():
                path = root / name
                path.write_text("#!/usr/bin/env bash\n" + text)
                path.chmod(0o755)
            env = os.environ | {"PATH": str(root) + ":" + os.environ["PATH"], "TEST_LOG": str(log)}
            subprocess.run(["bash", str(Path(__file__).parents[1] / "launch.sh")], env=env, check=True)
            self.assertEqual(log.read_text(), "bar reload\n")


if __name__ == "__main__":
    unittest.main()
