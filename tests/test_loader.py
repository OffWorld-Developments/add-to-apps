"""Check the genuine nautilus-python embedding, not just a Python import."""

import os
import shlex
import subprocess
from pathlib import Path

from add_to_applications.core import LauncherStore

ROOT = Path(__file__).resolve().parents[1]


def test_real_nautilus_python_loader(tmp_path, request):
    candidates = [
        Path(request.config.getoption("--nautilus-loader") or "/nonexistent"),
        Path("/usr/lib/nautilus/extensions-4/libnautilus-python.so"),
        Path("/usr/lib64/nautilus/extensions-4/libnautilus-python.so"),
    ]
    candidates.extend(
        Path("/usr/lib").glob("*-linux-gnu/nautilus/extensions-4/libnautilus-python.so")
    )
    loader = next((p for p in candidates if p.is_file()), None)
    assert loader is not None, "Install nautilus-python to run the loader integration test"
    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "libnautilus-extension-4", "gmodule-2.0"], text=True
    )
    binary = tmp_path / "loader-probe"
    subprocess.run(
        [
            "cc",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ROOT / "tests/loader_probe.c"),
            "-o",
            str(binary),
            *shlex.split(flags),
        ],
        check=True,
    )
    data = tmp_path / "data"
    subprocess.run(
        ["python3", str(ROOT / "tools/install.py"), "--stage", "--data-home", str(data)], check=True
    )
    source = tmp_path / "loader test.sh"
    source.write_text("#!/bin/sh\nexit 0\n")
    source.chmod(0o755)
    env = os.environ.copy()
    for key, subdir in [
        ("XDG_DATA_HOME", "data"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ]:
        env[key] = str(tmp_path / subdir)
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    env.update(XDG_RUNTIME_DIR=str(runtime), GIO_USE_VFS="local", GSETTINGS_BACKEND="memory")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    desktop = LauncherStore(data, tmp_path / "state").desktop_path(source)
    result = subprocess.run(
        ["dbus-run-session", "--", str(binary), str(loader), str(source), str(desktop)],
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "add and remove completed" in result.stdout
    assert "Traceback" not in result.stderr
    assert source.exists()
