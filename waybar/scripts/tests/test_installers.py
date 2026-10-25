#!/usr/bin/env python3
"""Verify user-local installer safety using only synthetic files.

Author: ae Orland
GitHub: https://github.com/ae-orlando
"""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
HEADER = "#!/usr/bin/env bash\n# Author: ae Orland\n# GitHub: https://github.com/ae-orlando\nexit 0\n"


def load(app):
    spec = importlib.util.spec_from_file_location("build_" + app, REPO / app / "backports" / ("build-" + app + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerTests(unittest.TestCase):
    def test_identical_reinstall_preserves_inode_and_uses_stable_wrappers(self):
        for app in ("waybar", "swaync"):
            with self.subTest(app=app), tempfile.TemporaryDirectory(prefix="installer-test-", dir="/tmp/opencode") as directory:
                root = Path(directory)
                env = {"HOME": str(root), "XDG_DATA_HOME": str(root / "data"), "XDG_CONFIG_HOME": str(root / "config")}
                with patch.dict(os.environ, env):
                    module = load(app)
                    for name, script in [(app, "start-" + app + ".sh"), ("waybar", "desktop-binaries.py")]:
                        path = root / "config" / name / "scripts" / script
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(HEADER)
                        path.chmod(0o755)
                    binary = root / "data/yoru" / app / app
                    binary.parent.mkdir(parents=True)
                    binary.write_text(HEADER)
                    binary.chmod(0o755)
                    binary.with_name("manifest.json").write_text("{}")
                    inode = binary.stat().st_ino
                    alias = root / ".local/bin" / app
                    alias.parent.mkdir(parents=True)
                    alias.symlink_to(binary)  # migrate the previous direct-binary alias
                    with patch.object(module.subprocess, "run") as run, redirect_stdout(io.StringIO()):
                        module.install(binary, "fixture-patch-hash")
                    self.assertEqual(binary.stat().st_ino, inode)
                    self.assertEqual(alias.resolve(), (root / "config" / app / "scripts" / ("start-" + app + ".sh")).resolve())
                    self.assertEqual(json.loads(binary.with_name("manifest.json").read_text())["patch_sha256"], "fixture-patch-hash")
                    run.assert_called_once_with(["systemctl", "--user", "daemon-reload"], check=True)
                    override = root / "config/systemd/user" / (app + ".service.d/yoru-backports.conf")
                    self.assertIn("start-" + app + ".sh", override.read_text())


if __name__ == "__main__":
    unittest.main()
