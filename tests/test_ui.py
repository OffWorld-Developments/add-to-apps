import os
import subprocess
import sys
from pathlib import Path


def test_native_rename_window(tmp_path):
    env = os.environ.copy()
    for key, subdir in [
        ("XDG_DATA_HOME", "data"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ]:
        env[key] = str(tmp_path / subdir)
    env.update(GSETTINGS_BACKEND="memory", GDK_BACKEND="x11", GTK_A11Y="none", GIO_USE_VFS="local")
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    result = subprocess.run(
        [
            "dbus-run-session",
            "--",
            "xvfb-run",
            "-a",
            sys.executable,
            str(Path(__file__).with_name("ui_probe.py")),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "validated and saved" in result.stdout
