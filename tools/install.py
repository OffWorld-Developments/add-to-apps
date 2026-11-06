#!/usr/bin/env python3
"""Install for the current user, or stage into an explicit XDG data directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from add_to_applications import APP_ID, VERSION  # noqa: E402
from add_to_applications.core import (  # noqa: E402
    LauncherError,
    atomic_write,
    quote_exec,
    read_regular,
    xdg_path,
)


def payload(data_home: Path) -> dict[Path, bytes]:
    destination = data_home / "add-to-applications"
    library = destination / "add_to_applications"
    runner = library / "runner.py"
    command = f"{quote_exec(sys.executable)} {quote_exec(str(runner))}"
    result = {
        library / path.name: path.read_bytes()
        for path in (ROOT / "src/add_to_applications").glob("*.py")
    }
    # Nautilus loads only top-level extension scripts. Importing the provider class
    # into this module is intentional: nautilus-python discovers it here.
    result[data_home / "nautilus-python/extensions/add_to_applications_extension.py"] = (
        "# Installed by Add to Applications.\n"
        "import sys\n"
        f"sys.path.insert(0, {str(destination)!r})\n"
        "from add_to_applications.nautilus_extension import AddToApplicationsExtension\n"
    ).encode()
    result[data_home / f"applications/{APP_ID}.desktop"] = (
        "[Desktop Entry]\nType=Application\nName=Add to Applications\n"
        f"Exec={command}\nIcon=application-x-executable\n"
        "NoDisplay=true\nTerminal=false\nDBusActivatable=true\n"
        "X-GNOME-UsesNotifications=true\n"
    ).encode()
    # D-Bus Exec uses shell argument parsing, not desktop-entry string unescaping.
    import shlex

    service_command = shlex.join([sys.executable, str(runner), "--gapplication-service"])
    result[data_home / f"dbus-1/services/{APP_ID}.service"] = (
        f"[D-BUS Service]\nName={APP_ID}\nExec={service_command}\n"
    ).encode()
    result[destination / "COPYING"] = (ROOT / "COPYING").read_bytes()
    return result


def check_dependencies():
    if sys.version_info < (3, 11):  # noqa: UP036 — explain requirements to older installers
        raise LauncherError("Python 3.11 or newer is required.")
    try:
        import gi

        for namespace, version in (
            ("GioUnix", "2.0"),
            ("Nautilus", "4.1"),
            ("Gtk", "4.0"),
            ("Adw", "1"),
        ):
            gi.require_version(namespace, version)
    except (ImportError, ValueError) as error:
        raise LauncherError(
            "Required GNOME 51 libraries are missing. See README.md for your distribution's "
            f"dependencies. ({error})"
        ) from error
    # The typelib alone is not enough: Files also needs the Python extension loader.
    candidates = [Path("/usr/lib"), Path("/usr/lib64"), Path("/usr/local/lib")]
    candidates.extend(Path("/usr/lib").glob("*-linux-gnu"))
    if not any(
        (root / "nautilus/extensions-4/libnautilus-python.so").is_file() for root in candidates
    ):
        raise LauncherError(
            "The Nautilus Python extension loader is missing. Install nautilus-python "
            "(Arch/Fedora) or python3-nautilus (Ubuntu), then run this installer again."
        )


def load_manifest(data_home: Path):
    manifest = data_home / "add-to-applications/manifest.json"
    raw = read_regular(manifest)
    if raw is None:
        return manifest, {}
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise LauncherError("The installation manifest is damaged.") from error
    if (
        not isinstance(value, dict)
        or value.get("application") != APP_ID
        or not isinstance(value.get("files"), dict)
        or not value["files"]
    ):
        raise LauncherError("The installation manifest belongs to another application.")
    files = value["files"]
    external_files = {
        "nautilus-python/extensions/add_to_applications_extension.py",
        f"applications/{APP_ID}.desktop",
        f"dbus-1/services/{APP_ID}.service",
        "add-to-applications/COPYING",
    }
    for relative, checksum in files.items():
        path = Path(relative)
        package_module = (
            len(path.parts) == 3
            and path.parts[:2] == ("add-to-applications", "add_to_applications")
            and path.suffix == ".py"
            and path.stem.isidentifier()
        )
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != relative
            or (relative not in external_files and not package_module)
        ):
            raise LauncherError("The installation manifest contains an invalid path.")
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise LauncherError("The installation manifest contains an invalid checksum.")
    return manifest, files


def install(data_home: Path):
    files = payload(data_home)
    manifest, previous = load_manifest(data_home)
    backups = {}
    for path in files:
        raw = read_regular(path)
        relative = str(path.relative_to(data_home))
        if raw is not None and relative not in previous:
            raise LauncherError(f"An unrelated file exists at {path}; it was left untouched.")
        if raw is not None and hashlib.sha256(raw).hexdigest() != previous[relative]:
            raise LauncherError(f"{path} was modified locally; it was left untouched.")
        backups[path] = raw
    try:
        for path, raw in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, raw, 0o644)
        content = {
            "application": APP_ID,
            "version": VERSION,
            "files": {
                str(path.relative_to(data_home)): hashlib.sha256(raw).hexdigest()
                for path, raw in files.items()
            },
        }
        atomic_write(manifest, json.dumps(content, indent=2).encode())
    except OSError:
        for path, raw in backups.items():
            if raw is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, raw, 0o644)
        raise
    print(f"Installed Add to Applications {VERSION} in {data_home}")
    print("Restart Files when convenient (nautilus -q), then open it again.")


def uninstall(data_home: Path):
    manifest, previous = load_manifest(data_home)
    if not previous:
        raise LauncherError("No installation was found in this data directory.")
    paths = []
    for relative, checksum in previous.items():
        path = data_home / relative
        raw = read_regular(path)
        if raw is not None and hashlib.sha256(raw).hexdigest() != checksum:
            raise LauncherError(f"{path} was modified locally; nothing was removed.")
        paths.append(path)
    for path in paths:
        path.unlink(missing_ok=True)
    manifest.unlink()
    # Remove empty installation directories only. Never remove user launchers,
    # executable files, state, or unrelated extensions.
    for directory in sorted({p.parent for p in paths}, key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    print("Uninstalled. Existing application shortcuts and executable files were kept.")
    print("Restart Files when convenient (nautilus -q), then open it again.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-home",
        type=Path,
        default=xdg_path("XDG_DATA_HOME", ".local/share"),
        help="explicit XDG data directory (also useful for staging)",
    )
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--check", action="store_true", help="check runtime dependencies only")
    parser.add_argument(
        "--stage",
        action="store_true",
        help="stage files without checking this machine's dependencies",
    )
    args = parser.parse_args()
    if args.check and (args.stage or args.uninstall):
        parser.error("--check cannot be combined with --stage or --uninstall")
    if os.getuid() == 0:
        parser.error("Run as your normal user, without sudo.")
    if not args.data_home.is_absolute():
        parser.error("--data-home must be an absolute path")
    try:
        if not args.uninstall and not args.stage:
            check_dependencies()
        if args.check:
            print("All runtime dependencies are available.")
            return 0
        (uninstall if args.uninstall else install)(args.data_home)
    except (OSError, ValueError, LauncherError) as error:
        print(f"Installation error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
