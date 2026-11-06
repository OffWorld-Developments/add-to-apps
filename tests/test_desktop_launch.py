"""Launch synthetic fixtures through GLib, not a second copy of our parser."""

import json
import subprocess
import time

import gi
import pytest

gi.require_version("GioUnix", "2.0")
from gi.repository import GioUnix  # noqa: E402


@pytest.mark.parametrize(
    "name",
    [
        "normal",
        "space in name.sh",
        "quote\"and'apostrophe",
        "dollar$HOME`id`",
        "back\\slash",
        "semi;colon&pipe|",
        "percent%F%u%%",
        "equal=sign",
        "Café-日本語",
        "(brackets)[square]#hash",
        "leading and trailing  ",
    ],
)
def test_real_desktop_launch_handles_literal_filename_and_cwd(store, script, tmp_path, name):
    # Each fixture reports what actually ran and its working directory.
    source = script(
        "parent with space/" + name,
        content=(
            b"#!/usr/bin/python3\nimport json,os,sys\n"
            b"open('result.json','w').write(json.dumps({'argv':sys.argv,'cwd':os.getcwd()}))\n"
        ),
    )
    change = store.add(source)
    validation = subprocess.run(["desktop-file-validate", str(change.desktop)], capture_output=True)
    assert validation.returncode == 0, validation.stderr.decode()
    app = GioUnix.DesktopAppInfo.new_from_filename(str(change.desktop))
    assert app is not None
    assert app.get_display_name() == change.name
    assert app.launch([], None)
    output = source.parent / "result.json"
    deadline = time.monotonic() + 5
    while not output.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    result = json.loads(output.read_text())
    assert result == {"argv": [str(source)], "cwd": str(source.parent)}


def test_launcher_still_works_after_executable_is_replaced(store, script):
    source = script(content=b"#!/bin/sh\nprintf first > result\n")
    change = store.add(source)
    source.write_bytes(b"#!/bin/sh\nprintf second > result\n")
    app = GioUnix.DesktopAppInfo.new_from_filename(str(change.desktop))
    app.launch([], None)
    output = source.parent / "result"
    deadline = time.monotonic() + 5
    while not output.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert output.read_text() == "second"
