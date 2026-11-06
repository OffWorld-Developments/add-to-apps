import concurrent.futures
import os
import stat
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from add_to_applications.core import (
    UNDO_SECONDS,
    LauncherError,
    LauncherStore,
    icon_for,
    source_path,
    validate_name,
    xdg_path,
)


def test_add_is_one_operation_and_does_not_run_executable(store, script, tmp_path):
    marker = tmp_path / "ran"
    source = script(content=f"#!/bin/sh\ntouch '{marker}'\n".encode())
    change = store.add(source)
    assert change.name == "My tool"
    assert change.token
    assert store.contains(source)
    assert not marker.exists()
    assert stat.S_IMODE(change.desktop.stat().st_mode) == 0o644
    assert "Terminal=false" in change.desktop.read_text()
    result = subprocess.run(["desktop-file-validate", str(change.desktop)], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()


def test_repeat_add_preserves_name_and_original_undo(store, script):
    source = script()
    first = store.add(source)
    second = store.add(source)
    assert second.token is None
    assert first.desktop.read_bytes() == second.desktop.read_bytes()
    store.undo(first.token)
    assert not store.contains(source)


def test_rename_remove_and_undo_are_durable(store, script):
    source = script()
    store.add(source)
    renamed = store.rename(source, "My useful app")
    assert store.name(source) == "My useful app"
    # A brand new process/store can undo from the journal alone.
    fresh = LauncherStore(store.applications.parent, store.state.parent)
    fresh.undo(renamed.token)
    assert fresh.name(source) == "My tool"
    removed = fresh.remove(source)
    assert source.exists()
    assert not fresh.contains(source)
    fresh.undo(removed.token)
    assert fresh.contains(source)


def test_undo_never_overwrites_a_later_change(store, script):
    source = script()
    added = store.add(source)
    renamed = store.rename(source, "Second name")
    with pytest.raises(LauncherError, match="changed since"):
        store.undo(added.token)
    assert store.name(source) == "Second name"
    renamed.desktop.write_text(renamed.desktop.read_text() + "Comment=External edit\n")
    with pytest.raises(LauncherError, match="changed since"):
        store.undo(renamed.token)


def test_old_remove_undo_does_not_revive_after_add_remove_cycle(store, script):
    source = script()
    store.add(source)
    removed = store.remove(source)
    store.add(source)
    store.remove(source)
    with pytest.raises(LauncherError, match="changed since"):
        store.undo(removed.token)


def test_undo_does_not_revive_older_notifications(store, script):
    source = script()
    added = store.add(source)
    renamed = store.rename(source, "New name")
    store.undo(renamed.token)
    with pytest.raises(LauncherError, match="changed since"):
        store.undo(added.token)
    with pytest.raises(LauncherError, match="expired or was already used"):
        store.undo(renamed.token)


@pytest.mark.parametrize("token", ["../../passwd", "", "f" * 33, "G" * 32])
def test_invalid_undo_tokens(store, token):
    with pytest.raises(LauncherError, match="invalid"):
        store.undo(token)


def test_expired_undo_is_pruned(store, script):
    added = store.add(script())
    journal = store.state / f"{added.token}.undo.json"
    old = time.time() - UNDO_SECONDS - 1
    os.utime(journal, (old, old))
    with pytest.raises(LauncherError, match="expired"):
        store.undo(added.token)
    assert not journal.exists()


@pytest.mark.parametrize("raw", [b"", b"not json", b"{}", b'{"version":1}'])
def test_damaged_journal_fails_safely(store, script, raw):
    added = store.add(script())
    (store.state / f"{added.token}.undo.json").write_bytes(raw)
    with pytest.raises(LauncherError, match="damaged"):
        store.undo(added.token)
    assert added.desktop.exists()


@pytest.mark.parametrize("name", ["", "  ", "a\nb", "a\tb", "a" * 121, "a\x00b"])
def test_invalid_names(name):
    with pytest.raises(LauncherError):
        validate_name(name)


def test_names_and_renaming_preserve_other_options(store, script):
    source = script("my-cool_tool.AppImage")
    added = store.add(source)
    assert added.name == "My cool tool"
    added.desktop.write_text(added.desktop.read_text().replace("Terminal=false", "Terminal=true"))
    renamed = store.rename(source, "  Café \\ [beta]  ")
    assert store.name(source) == "Café \\ [beta]"
    assert "Terminal=true" in renamed.desktop.read_text()
    assert store.rename(source, "Café \\ [beta]").token is None


def test_same_name_different_directories_do_not_collide(store, script):
    a, b = script("a/tool"), script("b/tool")
    assert store.add(a).desktop != store.add(b).desktop


def test_symlink_identity_is_preserved(store, script, tmp_path):
    source = script()
    link = tmp_path / "stable"
    link.symlink_to(source)
    change = store.add(link)
    assert str(link) in change.desktop.read_text()
    assert not store.contains(source)


def test_remove_works_after_executable_is_missing(store, script):
    source = script()
    store.add(source)
    source.unlink()
    change = store.remove(source)
    assert not change.desktop.exists()


def test_enables_owner_execute_but_undo_keeps_permission(store, script):
    source = script(executable=False)
    change = store.add(source)
    assert stat.S_IMODE(source.stat().st_mode) == 0o744
    store.undo(change.token)
    assert source.stat().st_mode & stat.S_IXUSR


def test_failure_rolls_back_permission_and_leaves_no_partial_entry(store, script):
    source = script(executable=False)
    with patch("add_to_applications.core.render_entry", side_effect=OSError("Disk full")):
        with pytest.raises(OSError):
            store.add(source)
    assert stat.S_IMODE(source.stat().st_mode) == 0o644
    assert not store.desktop_path(source).exists()


def test_failed_commit_restores_previous_entry(store, script):
    from add_to_applications import core

    source = script()
    added = store.add(source)
    before = added.desktop.read_bytes()
    original = core.atomic_write

    def fail_revision(path, *args):
        if path.name.endswith(".revision") and args[0] != added.token.encode():
            raise OSError("Disk full")
        return original(path, *args)

    with patch.object(core, "atomic_write", side_effect=fail_revision):
        with pytest.raises(OSError):
            store.rename(source, "Should not stick")
    assert added.desktop.read_bytes() == before
    store.undo(added.token)


@pytest.mark.parametrize(
    "content", [b"hello", b"MZwindows", b"#!/bin/sh", b"#!relative\n", b"\x7fELF"]
)
def test_rejects_non_programs_even_if_executable(store, script, content):
    source = script(content=content)
    with pytest.raises(LauncherError, match="not a Linux executable"):
        store.add(source)


def test_accepts_native_executable(store):
    change = store.add(Path("/usr/bin/true"))
    assert change.desktop.exists()


def test_rejects_directory_and_fifo_without_blocking(store, tmp_path):
    with pytest.raises(LauncherError):
        store.add(tmp_path)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(LauncherError):
        store.add(fifo)


def test_never_overwrites_unmanaged_file_or_follows_launcher_symlink(store, script, tmp_path):
    source = script()
    desktop = store.desktop_path(source)
    desktop.parent.mkdir(parents=True)
    desktop.write_text("An unrelated file")
    with pytest.raises(LauncherError, match="unrelated"):
        store.add(source)
    assert desktop.read_text() == "An unrelated file"
    desktop.unlink()
    target = tmp_path / "valuable"
    target.write_text("Keep me")
    desktop.symlink_to(target)
    with pytest.raises(LauncherError, match="safely read"):
        store.add(source)
    assert target.read_text() == "Keep me"


def test_concurrent_adds_create_one_launcher(store, script):
    source = script()
    # Separate opens + flock also serialize threads on Linux.
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: store.add(source), range(12)))
    assert sum(change.token is not None for change in results) == 1
    assert len(list(store.applications.glob("*.desktop"))) == 1


def test_local_sidecar_icons_and_fallback(script, tmp_path):
    source = script()
    assert icon_for(source) == "application-x-executable"
    icon = source.with_suffix(".png")
    icon.write_bytes(b"image")
    assert icon_for(source) == str(icon)
    icon.unlink()
    icon.symlink_to(source)
    assert icon_for(source) == "application-x-executable"


def test_xdg_relative_values_are_ignored(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "relative")
    assert xdg_path("XDG_DATA_HOME", ".local/share") == Path.home() / ".local/share"


def test_invalid_path_cannot_inject_desktop_keys():
    with pytest.raises(LauncherError):
        source_path("bad\nExec=malicious")


def test_oversized_desktop_is_rejected(store, script):
    source = script()
    change = store.add(source)
    change.desktop.write_bytes(b"x" * (256 * 1024 + 1))
    with pytest.raises(LauncherError, match="too large"):
        store.remove(source)


@pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"])
def test_unicode_line_separators_cannot_split_launcher_fields(separator):
    with pytest.raises(LauncherError):
        source_path(f"my{separator}Exec=bad")
    with pytest.raises(LauncherError):
        validate_name(f"my{separator}name")
