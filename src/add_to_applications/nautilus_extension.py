"""Nautilus 4.1 extension for GNOME 51. Never import GTK into Files."""

import gettext
import logging
import sys
from pathlib import Path

import gi

gi.require_version("Nautilus", "4.1")
from gi.repository import Gio, GLib, GObject, Nautilus  # noqa: E402

from .core import LauncherError, LauncherStore  # noqa: E402

_ = gettext.translation("add-to-applications", fallback=True).gettext
LOG = logging.getLogger(__name__)


class AddToApplicationsExtension(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        super().__init__()
        self.store = LauncherStore()
        self._children = set()

    def get_file_items(self, files):
        if len(files) != 1:
            return []
        file = files[0]
        location = file.get_location()
        if not location or not location.is_native() or file.is_directory() or file.is_gone():
            return []
        if file.get_file_type() not in (Gio.FileType.REGULAR, Gio.FileType.SYMBOLIC_LINK):
            return []
        path = location.get_path()
        if not path or Path(path).suffix.lower() == ".desktop":
            return []
        try:
            managed = self.store.contains(path)
        except (LauncherError, OSError):
            LOG.warning("Could not inspect launcher state", exc_info=True)
            return []
        # Use Nautilus's cached content type; never sniff or execute a selected file
        # while building a context menu (the source might live on a slow mount).
        mime = file.get_mime_type() or "application/octet-stream"
        executable = Gio.content_type_is_a(mime, "application/x-executable") or mime in {
            "application/x-pie-executable",
            "application/x-appimage",
            "application/x-elf",
        }
        if not managed and not executable:
            return []
        actions = (
            [("remove", _("Remove from Applications")), ("rename", _("Rename in Applications…"))]
            if managed
            else [("add", _("Add to Applications"))]
        )
        items = []
        for action, label in actions:
            item = Nautilus.MenuItem(name=f"AddToApplications::{action}", label=label)
            item.connect("activate", self._activate, action, path)
            items.append(item)
        return items

    def _activate(self, _item, action, path):
        try:
            child = Gio.Subprocess.new(
                [sys.executable, str(Path(__file__).with_name("runner.py")), f"--{action}", path],
                Gio.SubprocessFlags.NONE,
            )
            self._children.add(child)
            child.wait_async(None, self._finished)
        except GLib.Error:
            LOG.exception("Could not start Add to Applications")

    def _finished(self, child, result):
        try:
            child.wait_finish(result)
        except GLib.Error:
            LOG.exception("Add to Applications helper failed")
        finally:
            self._children.discard(child)
            self.emit("items-updated")
