"""Short-lived helper; GTK is loaded only for the optional rename window."""

from __future__ import annotations

import argparse
import base64
import gettext
import logging
import os
import shutil
import sys
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GioUnix", "2.0")
from gi.repository import Gio, GioUnix, GLib  # noqa: E402

from . import APP_ID  # noqa: E402
from .core import Change, LauncherError, LauncherStore, source_path  # noqa: E402

_ = gettext.translation("add-to-applications", fallback=True).gettext
LOG = logging.getLogger(__name__)


def existing_application(path: Path):
    """Respect launchers supplied by other applications; never modify them."""
    for app in GioUnix.DesktopAppInfo.get_all():
        if not app.should_show():
            continue
        # Also recognize our encoded paths and stable-symlink aliases.
        if isinstance(app, GioUnix.DesktopAppInfo):
            encoded = app.get_string("X-AddToApplications-Source")
            if encoded:
                try:
                    if path.samefile(os.fsdecode(base64.b64decode(encoded, validate=True))):
                        return app.get_display_name()
                except (OSError, ValueError):
                    pass
        executable = app.get_executable()
        if not executable:
            continue
        resolved = executable if Path(executable).is_absolute() else shutil.which(executable)
        try:
            if resolved and path.samefile(resolved):
                return app.get_display_name()
        except OSError:
            continue
    return None


def build_rename_window(store, source, on_save, on_close):
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk

    Adw.init()
    window = Adw.Window(title=_("Rename in Applications"), default_width=420, resizable=False)
    view = Adw.ToolbarView()
    header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
    cancel = Gtk.Button(label=_("Cancel"))
    save = Gtk.Button(label=_("Rename"))
    save.add_css_class("suggested-action")
    header.pack_start(cancel)
    header.pack_end(save)
    view.add_top_bar(header)
    box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=16,
        margin_top=24,
        margin_bottom=24,
        margin_start=24,
        margin_end=24,
    )
    group = Adw.PreferencesGroup()
    entry = Adw.EntryRow(title=_("Name"), text=store.name(source), activates_default=True)
    group.add(entry)
    box.append(group)
    hint = Gtk.Label(
        label=_("Changes the name in Applications. Your file keeps its name."), wrap=True, xalign=0
    )
    hint.add_css_class("dim-label")
    box.append(hint)
    error_label = Gtk.Label(wrap=True, xalign=0, visible=False)
    error_label.add_css_class("error")
    box.append(error_label)
    view.set_content(box)
    window.set_content(view)
    window.set_default_widget(save)

    def validate(*_args):
        from .core import validate_name

        try:
            validate_name(entry.get_text())
            save.set_sensitive(True)
        except LauncherError:
            save.set_sensitive(False)

    def submit(*_args):
        try:
            change = store.rename(source, entry.get_text())
        except (LauncherError, OSError) as error:
            error_label.set_text(str(error))
            error_label.set_visible(True)
            return
        on_save(change)
        window.close()

    def close(*_args):
        window.destroy()
        on_close()
        return True

    entry.connect("changed", validate)
    save.connect("clicked", submit)
    cancel.connect("clicked", lambda *_: window.close())
    window.connect("close-request", close)
    # Escape dismisses without changing anything.
    controller = Gtk.ShortcutController()
    controller.add_shortcut(
        Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("Escape"),
            Gtk.CallbackAction.new(lambda *_: (window.close(), True)[1]),
        )
    )
    window.add_controller(controller)
    entry.grab_focus()
    return window


class Application(Gio.Application):
    def __init__(self, store=None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.store = store or LauncherStore()
        self._windows = set()

    def do_startup(self):
        Gio.Application.do_startup(self)
        action = Gio.SimpleAction.new("undo", GLib.VariantType.new("s"))
        action.connect("activate", self._undo_action)
        self.add_action(action)

    def do_activate(self):
        # Clicking a notification body does not open a manager or a setup screen.
        pass

    def _settle(self):
        # Let asynchronous notification delivery finish before this helper exits.
        self.hold()
        GLib.timeout_add(500, self._release_once)

    def _release_once(self):
        self.release()
        return GLib.SOURCE_REMOVE

    def _notify(self, title, body=None, change: Change | None = None):
        notification = Gio.Notification.new(title)
        notification.set_icon(Gio.ThemedIcon.new("application-x-executable"))
        if body:
            notification.set_body(body)
        if change and change.token:
            notification.add_button_with_target(
                _("Undo"), "app.undo", GLib.Variant("s", change.token)
            )
        self.send_notification(change.token if change and change.token else "status", notification)
        self._settle()

    def _error(self, error):
        LOG.warning("Launcher action failed: %s", error)
        message = (
            str(error)
            if isinstance(error, LauncherError)
            else _(
                "The change could not be saved. "
                "Check that the file and your Applications folder are accessible."
            )
        )
        self._notify(_("Couldn’t update Applications"), message)

    def _undo_action(self, _action, value):
        try:
            token = value.get_string()
            change = self.store.undo(token)
            self.withdraw_notification(token)
            self._notify(
                _("Change undone"), _("“%s” was restored to its previous state.") % change.name
            )
        except (LauncherError, OSError) as error:
            self._error(error)

    def _rename(self, source):
        holder = {}

        def saved(change):
            self._notify(_("Renamed to “%s”") % change.name, change=change)

        def closed():
            self._windows.discard(holder["window"])
            self.release()

        window = build_rename_window(self.store, source, saved, closed)
        holder["window"] = window
        self._windows.add(window)
        self.hold()
        window.present()

    def do_command_line(self, command_line):
        parser = argparse.ArgumentParser(description=_("Add an executable to Applications."))
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--add", metavar="FILE")
        group.add_argument("--remove", metavar="FILE")
        group.add_argument("--rename", metavar="FILE")
        group.add_argument("--undo", metavar="TOKEN")
        try:
            args = parser.parse_args(command_line.get_arguments()[1:])
        except SystemExit as error:
            return int(error.code)
        try:
            if args.add:
                source = source_path(args.add)
                existing = existing_application(source) if not self.store.contains(source) else None
                if existing:
                    self._notify(_("“%s” is already in Applications") % existing)
                else:
                    change = self.store.add(source)
                    title = (
                        _("Added “%s” to Applications")
                        if change.token
                        else _("“%s” is already in Applications")
                    ) % change.name
                    self._notify(title, _("Keep the executable in its current location."), change)
            elif args.remove:
                change = self.store.remove(args.remove)
                self._notify(
                    _("Removed “%s” from Applications") % change.name,
                    _("Your executable file was kept."),
                    change,
                )
            elif args.rename:
                self._rename(source_path(args.rename))
            elif args.undo:
                self._undo_action(None, GLib.Variant("s", args.undo))
        except (LauncherError, OSError) as error:
            self._error(error)
            return 1
        return 0


def main():
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(_("Add to Applications"))
    logging.basicConfig(level=logging.WARNING)
    return Application().run(sys.argv)
