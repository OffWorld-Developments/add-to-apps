"""Check the genuine nautilus-python embedding, not just a Python import."""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from add_to_applications.core import LauncherStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def loader_probe(tmp_path, request):
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
    return binary, loader


def test_real_nautilus_python_loader(tmp_path, loader_probe):
    binary, loader = loader_probe
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


def test_default_install_persists_across_fresh_sessions_without_source_checkout(
    tmp_path, loader_probe
):
    """Discard source/runtime state, then let the real loader discover files again.

    This models a new Files process at login. It does not reboot the test host.
    """
    binary, loader = loader_probe
    checkout = tmp_path / "downloaded-source"
    checkout.mkdir()
    shutil.copytree(ROOT / "src", checkout / "src", ignore=shutil.ignore_patterns("__pycache__"))
    (checkout / "tools").mkdir()
    shutil.copyfile(ROOT / "tools/install.py", checkout / "tools/install.py")
    shutil.copyfile(ROOT / "COPYING", checkout / "COPYING")
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    for key in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME",
                "DBUS_SESSION_BUS_ADDRESS", "PYTHONPATH", "PYTHONHOME",
                "PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE"):
        env.pop(key, None)
    env.update(HOME=str(home), XDG_DATA_DIRS="/usr/share", GIO_USE_VFS="local",
               GSETTINGS_BACKEND="memory")
    # The default installation, not an explicit --data-home or a staging copy.
    subprocess.run([sys.executable, str(checkout / "tools/install.py")], env=env, check=True)
    unavailable_checkout = tmp_path / "unavailable-source"
    checkout.rename(unavailable_checkout)
    data = home / ".local/share"
    entry_point = data / "nautilus-python/extensions/add_to_applications_extension.py"
    assert str(checkout) not in entry_point.read_text()
    source = tmp_path / "persistent sample.sh"
    source.write_text("#!/bin/sh\nexit 0\n")
    source.chmod(0o755)
    desktop = LauncherStore(data, home / ".local/state").desktop_path(source)
    for session in range(3):
        runtime = tmp_path / f"runtime-{session}"
        runtime.mkdir(mode=0o700)
        env["XDG_RUNTIME_DIR"] = str(runtime)
        arguments = []
        if session == 2:
            subprocess.run([sys.executable, str(unavailable_checkout / "tools/install.py"),
                            "--uninstall"], env=env, check=True)
            arguments = ["--expect-uninstalled"]
        result = subprocess.run(
            ["dbus-run-session", "--", str(binary), str(loader), str(source), str(desktop),
             *arguments], env=env, capture_output=True, text=True, timeout=25,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Traceback" not in result.stderr
        assert ("absent after uninstall" if session == 2 else "add and remove completed") in result.stdout
        status = subprocess.run([sys.executable, str(unavailable_checkout / "tools/install.py"),
                                 "--status"], env=env, capture_output=True, text=True)
        assert status.returncode == (1 if session == 2 else 0), status.stdout + status.stderr
    assert source.exists()
