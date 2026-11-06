import os
import subprocess
import sys
from pathlib import Path


def test_notification_and_undo_via_cold_dbus_activation(tmp_path):
    env = os.environ.copy()
    for key, subdir in [
        ("XDG_DATA_HOME", "data with space"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ]:
        env[key] = str(tmp_path / subdir)
    env.update(GSETTINGS_BACKEND="memory", GIO_USE_VFS="local")
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    result = subprocess.run(
        [
            "dbus-run-session",
            "--",
            sys.executable,
            str(Path(__file__).with_name("session_probe.py")),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"undo": "cold-activated"' in result.stdout
