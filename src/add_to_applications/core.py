"""Launcher storage. No GTK, D-Bus, subprocesses, or execution of selected files.

All mutations are serialized across processes. Desktop entries are replaced atomically;
undo compares both the operation generation and the exact file contents.
"""

from __future__ import annotations

import base64
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

PREFIX = "add-to-applications-"
MAX_ENTRY_SIZE = 256 * 1024
UNDO_SECONDS = 7 * 24 * 60 * 60
MARKER = "X-AddToApplications-Managed=true"
SCRIPT_SUFFIXES = (".appimage", ".sh", ".py", ".pl", ".rb", ".run", ".bin")


class LauncherError(Exception):
    """An error safe to explain to the user."""


@dataclass(frozen=True)
class Change:
    name: str
    token: str | None
    desktop: Path


def has_control_characters(value: str) -> bool:
    return any(unicodedata.category(char) in {"Cc", "Cs", "Zl", "Zp"} for char in value)


def xdg_path(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable)
    # The XDG specification requires absolute paths; ignore relative values.
    return Path(value) if value and os.path.isabs(value) else Path.home() / fallback


def source_path(path: str | Path) -> Path:
    """Keep symlink spelling: a stable symlink can point at successive releases."""
    value = os.path.abspath(os.fspath(path))
    if has_control_characters(value):
        raise LauncherError("File names containing control characters are not supported.")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise LauncherError("The file name must be valid UTF-8.") from error
    return Path(value)


def desktop_id(path: Path) -> str:
    return PREFIX + hashlib.sha256(os.fsencode(path)).hexdigest() + ".desktop"


def validate_name(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 120 or has_control_characters(value):
        raise LauncherError("Use a name of 1–120 characters, without line breaks.")
    return value


def suggested_name(path: Path) -> str:
    name = path.name
    for suffix in SCRIPT_SUFFIXES:
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    name = re.sub(r"[_-]+", " ", name).strip()
    return validate_name((name[:1].upper() + name[1:])[:120] or "Application")


def escape_string(value: str) -> str:
    # KeyFile string escaping is separate from Exec argument quoting.
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace(" ", "\\s")
    )


def quote_exec(value: str) -> str:
    if "%" in value:
        raise LauncherError("Internal command contains a desktop field code.")
    quoted = '"' + re.sub(r'(["`$\\])', r"\\\1", value) + '"'
    return quoted.replace("\\", "\\\\")


def executable_command(path: Path) -> str:
    value = str(path)
    if "%" in value or "=" in value:
        # The spec prohibits '=' in executable paths and leaves percent field codes
        # inside quotes undefined. Encode the path as inert data, then exec without
        # a shell. The launcher remains usable after uninstalling this extension.
        encoded = base64.b64encode(os.fsencode(path)).decode("ascii")
        code = "import base64,os,sys;p=base64.b64decode(sys.argv[1]);os.execv(p,[p])"
        return " ".join(quote_exec(arg) for arg in (sys.executable, "-c", code, encoded))
    return quote_exec(value)


def icon_for(path: Path) -> str:
    stem = path.name
    for suffix in SCRIPT_SUFFIXES:
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    for name in (f"{stem}.svg", f"{stem}.png", "icon.svg", "icon.png"):
        candidate = path.parent / name
        try:
            info = candidate.lstat()
            if stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 2 * 1024 * 1024:
                return str(candidate)
        except OSError:
            continue
    return "application-x-executable"


def render_entry(path: Path, name: str, revision: str) -> str:
    values = {
        "Type": "Application",
        "Version": "1.0",
        "Name": escape_string(validate_name(name)),
        "Exec": executable_command(path),
        "Path": escape_string(str(path.parent)),
        "Icon": escape_string(icon_for(path)),
        "Terminal": "false",
        "Categories": "Utility;",
        "StartupNotify": "false",
        "X-AddToApplications-Managed": "true",
        "X-AddToApplications-Source": base64.b64encode(os.fsencode(path)).decode("ascii"),
        "X-AddToApplications-Revision": revision,
    }
    return "[Desktop Entry]\n" + "".join(f"{key}={value}\n" for key, value in values.items())


def read_regular(path: Path, limit: int = MAX_ENTRY_SIZE) -> bytes | None:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise LauncherError(f"Cannot safely read {path.name}.") from error
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise LauncherError(f"{path.name} is not a regular file.")
        data = handle.read(limit + 1)
        if len(data) > limit:
            raise LauncherError(f"{path.name} is too large.")
        return data


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    fd, temp = tempfile.mkstemp(prefix=".add-to-applications-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp)


class LauncherStore:
    def __init__(self, data_home: Path | None = None, state_home: Path | None = None):
        self.applications = (
            data_home or xdg_path("XDG_DATA_HOME", ".local/share")
        ) / "applications"
        self.state = (
            state_home or xdg_path("XDG_STATE_HOME", ".local/state")
        ) / "add-to-applications"

    def desktop_path(self, path: str | Path) -> Path:
        return self.applications / desktop_id(source_path(path))

    @contextlib.contextmanager
    def _locked(self):
        self.applications.mkdir(parents=True, exist_ok=True)
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.state / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise LauncherError("The launcher lock is not owned by your user.")
            fcntl.flock(fd, fcntl.LOCK_EX)
            self._prune_undo()
            yield
        finally:
            os.close(fd)

    def _prune_undo(self):
        for path in self.state.glob("*.undo.json"):
            with contextlib.suppress(OSError):
                if path.lstat().st_mtime < time.time() - UNDO_SECONDS:
                    path.unlink()

    def _read_managed(self, source: Path) -> bytes | None:
        raw = read_regular(self.desktop_path(source))
        if raw is not None:
            expected = (
                "X-AddToApplications-Source=" + base64.b64encode(os.fsencode(source)).decode()
            )
            try:
                lines = raw.decode("utf-8").split("\n")
            except UnicodeError as error:
                raise LauncherError("The launcher file is not valid UTF-8.") from error
            if (
                not lines
                or MARKER not in lines
                or expected not in lines
                or lines[0] != "[Desktop Entry]"
            ):
                raise LauncherError(
                    "An unrelated launcher uses this file name; it was left untouched."
                )
        return raw

    def contains(self, source: str | Path) -> bool:
        return self._read_managed(source_path(source)) is not None

    def name(self, source: str | Path) -> str:
        raw = self._read_managed(source_path(source))
        if raw is None:
            raise LauncherError("This file has not been added to Applications.")
        for line in raw.decode().split("\n"):
            if line.startswith("Name="):
                return re.sub(
                    r"\\([snrt\\])",
                    lambda m: {"s": " ", "n": "\n", "r": "\r", "t": "\t", "\\": "\\"}[m[1]],
                    line[5:],
                )
        raise LauncherError("The launcher has no name.")

    def _change(
        self, source: Path, before: bytes | None, after: bytes | None, name: str, token: str
    ) -> Change:
        desktop = self.desktop_path(source)
        record = {
            "version": 1,
            "source": str(source),
            "name": name,
            "created": time.time(),
            "token": token,
            "before": before.decode() if before is not None else None,
            "after": after.decode() if after is not None else None,
        }
        undo_path = self.state / f"{token}.undo.json"
        revision_path = self.state / (desktop.name + ".revision")
        old_revision = read_regular(revision_path)
        # Write undo first. An interrupted operation leaves a harmless stale journal,
        # which cannot pass the revision/content comparison.
        atomic_write(undo_path, json.dumps(record, ensure_ascii=False).encode())
        try:
            if after is None:
                desktop.unlink()
            else:
                atomic_write(desktop, after, 0o644)
            atomic_write(revision_path, token.encode())
        except OSError:
            if before is None:
                desktop.unlink(missing_ok=True)
            else:
                atomic_write(desktop, before, 0o644)
            if old_revision is None:
                revision_path.unlink(missing_ok=True)
            else:
                atomic_write(revision_path, old_revision)
            undo_path.unlink(missing_ok=True)
            raise
        return Change(name, token, desktop)

    def add(self, path: str | Path) -> Change:
        source = source_path(path)
        with self._locked():
            before = self._read_managed(source)
            if before is not None:
                return Change(self.name(source), None, self.desktop_path(source))
            # Never run the selected file to determine its type or extract metadata.
            fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK)
            changed_mode = False
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode):
                    raise LauncherError(
                        "Choose a local executable file or a script with a #! line."
                    )
                magic = os.read(fd, 256)
                is_elf = len(magic) >= 20 and magic[:4] == b"\x7fELF"
                if is_elf:
                    endian = {1: "little", 2: "big"}.get(magic[5])
                    is_elf = endian is not None and int.from_bytes(magic[16:18], endian) in (2, 3)
                if not (is_elf or (magic.startswith(b"#!/") and b"\n" in magic)):
                    raise LauncherError(
                        "This is not a Linux executable or a script with a #! line."
                    )
                if not os.access(source, os.X_OK):
                    if info.st_uid != os.getuid():
                        raise LauncherError(
                            "You do not own this file and cannot make it executable."
                        )
                    os.fchmod(fd, stat.S_IMODE(info.st_mode) | stat.S_IXUSR)
                    changed_mode = True
                    if not os.access(source, os.X_OK):
                        raise LauncherError(
                            "This location does not allow running executable files."
                        )
                token = uuid.uuid4().hex
                name = suggested_name(source)
                change = self._change(
                    source, None, render_entry(source, name, token).encode(), name, token
                )
                return change
            except BaseException:
                if changed_mode:
                    os.fchmod(fd, stat.S_IMODE(info.st_mode))
                raise
            finally:
                os.close(fd)

    def remove(self, path: str | Path) -> Change:
        source = source_path(path)
        with self._locked():
            before = self._read_managed(source)
            if before is None:
                raise LauncherError("This file has not been added to Applications.")
            return self._change(source, before, None, self.name(source), uuid.uuid4().hex)

    def rename(self, path: str | Path, name: str) -> Change:
        source, name = source_path(path), validate_name(name)
        with self._locked():
            before = self._read_managed(source)
            if before is None:
                raise LauncherError("This file has not been added to Applications.")
            if self.name(source) == name:
                return Change(name, None, self.desktop_path(source))
            token = uuid.uuid4().hex
            # Preserve other fields, including any user-specified Terminal or icon.
            lines = before.decode().removesuffix("\n").split("\n")
            lines = [
                "Name=" + escape_string(name)
                if line.startswith("Name=")
                else "X-AddToApplications-Revision=" + token
                if line.startswith("X-AddToApplications-Revision=")
                else line
                for line in lines
            ]
            after = ("\n".join(lines) + "\n").encode()
            return self._change(source, before, after, name, token)

    def undo(self, token: str) -> Change:
        if not re.fullmatch(r"[0-9a-f]{32}", token):
            raise LauncherError("This Undo action is invalid.")
        with self._locked():
            undo_path = self.state / f"{token}.undo.json"
            raw = read_regular(undo_path, MAX_ENTRY_SIZE * 3)
            if raw is None:
                raise LauncherError("This Undo action has expired or was already used.")
            try:
                record = json.loads(raw)
                if record["version"] != 1 or record["token"] != token:
                    raise ValueError("Invalid journal")
                if time.time() - record["created"] > UNDO_SECONDS:
                    raise LauncherError("This Undo action has expired.")
                source = source_path(record["source"])
                name = validate_name(record["name"])
                before = record["before"].encode() if record["before"] is not None else None
                after = record["after"].encode() if record["after"] is not None else None
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                raise LauncherError("This Undo record is damaged.") from error
            desktop = self.desktop_path(source)
            revision = self.state / (desktop.name + ".revision")
            if read_regular(revision) != token.encode() or read_regular(desktop) != after:
                raise LauncherError(
                    "This launcher changed since that action; it was left untouched."
                )
            if before is None:
                desktop.unlink()
            else:
                atomic_write(desktop, before, 0o644)
            # Do not revive old notifications. Undo itself is a new generation.
            atomic_write(revision, uuid.uuid4().hex.encode())
            undo_path.unlink()
            return Change(name, None, desktop)
