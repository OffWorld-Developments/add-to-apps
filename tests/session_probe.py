"""Run under a private dbus-run-session; never touches the user's session bus."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from install import install  # noqa: E402

from add_to_applications import APP_ID  # noqa: E402
from add_to_applications.core import LauncherStore  # noqa: E402

data = Path(os.environ["XDG_DATA_HOME"])
install(data)
source = data.parent / "sample tool.sh"
source.write_text("#!/bin/sh\nexit 0\n")
source.chmod(0o755)
store = LauncherStore()
messages = []
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
bus.call_sync(
    "org.freedesktop.DBus",
    "/org/freedesktop/DBus",
    "org.freedesktop.DBus",
    "RequestName",
    GLib.Variant("(su)", ("org.gtk.Notifications", 0)),
    None,
    Gio.DBusCallFlags.NONE,
    5000,
    None,
)
node = Gio.DBusNodeInfo.new_for_xml("""
<node><interface name="org.gtk.Notifications">
<method name="AddNotification"><arg type="s" direction="in"/>
<arg type="s" direction="in"/><arg type="a{sv}" direction="in"/></method>
<method name="RemoveNotification"><arg type="s" direction="in"/>
<arg type="s" direction="in"/></method>
</interface></node>
""")


def on_method(_connection, _sender, _path, _interface, method, params, invocation):
    messages.append((method, params.unpack()))
    invocation.return_value(None)


bus.register_object("/org/gtk/Notifications", node.interfaces[0], on_method, None, None)
context = GLib.MainContext.default()


def until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        while context.pending():
            context.iteration(False)
        if time.monotonic() > deadline:
            raise AssertionError(f"Session probe timed out; notifications={messages!r}")
        time.sleep(0.01)
    while context.pending():
        context.iteration(False)


runner = data / "add-to-applications/add_to_applications/runner.py"
child = subprocess.Popen([sys.executable, str(runner), "--add", str(source)])
until(lambda: child.poll() is not None)
assert child.returncode == 0
until(lambda: any(method == "AddNotification" for method, _ in messages))
added = next(params for method, params in messages if method == "AddNotification")
app_id, token, notification = added
assert app_id == APP_ID
assert notification["title"] == "Added “Sample tool” to Applications", notification
assert notification["buttons"][0]["label"] == "Undo"
assert notification["buttons"][0]["action"] == "app.undo"
assert notification["buttons"][0]["target"] == token
assert store.contains(source)
assert not bus.call_sync(
    "org.freedesktop.DBus",
    "/org/freedesktop/DBus",
    "org.freedesktop.DBus",
    "NameHasOwner",
    GLib.Variant("(s)", (APP_ID,)),
    None,
    Gio.DBusCallFlags.NONE,
    5000,
    None,
).unpack()[0]

# Cold D-Bus activation must restore Undo after the original helper exited.
bus.call_sync(
    APP_ID,
    "/" + APP_ID.replace(".", "/"),
    "org.gtk.Actions",
    "Activate",
    GLib.Variant("(sava{sv})", ("undo", [GLib.Variant("s", token)], {})),
    None,
    Gio.DBusCallFlags.NONE,
    10000,
    None,
)
until(lambda: not store.contains(source))
until(lambda: any(method == "RemoveNotification" for method, _ in messages))
until(
    lambda: any(
        method == "AddNotification" and params[2]["title"] == "Change undone"
        for method, params in messages
    )
)
assert source.exists()
print(json.dumps({"notification": "delivered", "undo": "cold-activated", "source": "kept"}))
