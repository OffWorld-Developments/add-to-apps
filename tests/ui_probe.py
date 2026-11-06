"""Exercise the actual GTK 4/libadwaita rename window on an isolated display."""

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from add_to_applications.app import build_rename_window  # noqa: E402
from add_to_applications.core import LauncherStore  # noqa: E402

base = Path(os.environ["XDG_DATA_HOME"]).parent
source = base / "my_tool.sh"
source.write_text("#!/bin/sh\nexit 0\n")
source.chmod(0o755)
store = LauncherStore()
store.add(source)
changes, closed = [], []
window = build_rename_window(store, source, changes.append, lambda: closed.append(True))
window.present()
loop = GLib.MainLoop()


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from descendants(child)
        child = child.get_next_sibling()


def exercise():
    from gi.repository import Adw

    widgets = list(descendants(window))
    entry = next(w for w in widgets if isinstance(w, Adw.EntryRow))
    button = next(w for w in widgets if isinstance(w, Gtk.Button) and w.get_label() == "Rename")
    entry.set_text("   ")
    assert not button.get_sensitive()
    entry.set_text("My useful app")
    assert button.get_sensitive()
    button.emit("clicked")
    assert store.name(source) == "My useful app"
    assert len(changes) == 1 and changes[0].token
    assert closed == [True]
    loop.quit()
    return GLib.SOURCE_REMOVE


GLib.timeout_add(300, exercise)
GLib.timeout_add_seconds(5, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
loop.run()
assert changes, "Rename UI did not complete"
print("Rename window: validated and saved")
