# Architecture

The only ordinary interaction is a Nautilus file context-menu action. An installed
loader imports `AddToApplicationsExtension`, a `Nautilus.MenuProvider` using API
4.1. It uses cached file metadata and inspects only its small local launcher entry;
it does not read the selected executable while constructing the menu.

Clicking an action starts a separate Python helper with an argument vector, never
a shell command. The Files process imports neither GTK nor libadwaita. File I/O,
content validation, permission changes, and application enumeration happen in the
helper process. The optional rename window loads GTK 4/libadwaita only when used.

## Desktop entries

Entries live in `$XDG_DATA_HOME/applications` (normally
`~/.local/share/applications`). Their IDs use the SHA-256 of the absolute source
path, avoiding collisions between similarly named programs. The source path is
not resolved through symlinks, allowing a stable symlink to target newer versions.
Entries include a management marker and encoded source path. The tool refuses to
replace or remove an entry without its matching markers.

`Exec` uses the freedesktop desktop-entry quoting rules, including both layers of
backslash escaping. For source paths containing `%` or `=`, it invokes a tiny fixed
Python bootstrap with the base64-encoded path as inert data. This avoids undefined
field-code expansion and the specification's prohibition on `=` in executable
paths. The bootstrap calls `os.execv`; it never interpolates a path into Python or
shell source. Generated shortcuts do not depend on this extension's code remaining
installed. Python remains a runtime dependency for the special-path bootstrap.

`Path` is the source's parent folder. `Terminal=false` is deliberate: detecting
whether an arbitrary executable needs a terminal cannot be done reliably without
more user configuration. Metadata extraction never executes untrusted code.

## Mutations and Undo

The core uses only the Python standard library. Its writes are serialized by a
per-user `flock`; desktop files and journals use temporary files, `fsync`, and
atomic replacement. It rejects symlinks and non-regular files when reading its
own entry and state files. A failed ordinary commit rolls back the desktop entry
and permission change. This is not a multi-file database transaction: a machine
crash between writes can leave a completed change without a usable Undo record;
it cannot authorize an old Undo to overwrite a later generation.

Undo journals and generation files live in
`$XDG_STATE_HOME/add-to-applications` (normally `~/.local/state`). Journals keep
before/after entry contents, a random token, and a timestamp. Undo compares both
the token and exact current contents, including absence for a removal. An add/remove
cycle invalidates older actions even when the final file state looks identical.
Undo itself creates a new generation, so old notifications cannot be revived.
Expired journals are pruned on subsequent mutations after seven days. Generation
files remain to prevent reuse of old actions.

Notifications use `Gio.Notification`. A hidden helper desktop entry and a D-Bus
activation service let notification buttons restart the helper after it exits.
There is no polling daemon. Errors are logged and reported through notifications;
as with all GNOME notifications, Do Not Disturb may suppress banners.

## Installation

The installer uses the standard per-user Nautilus extension and D-Bus service
locations. It writes a checksum manifest, checks for unrelated or modified files
before any writes/removals, and rolls back an ordinary failed install. It never
installs distribution dependencies, closes Files windows, or deletes generated
launchers or executable files during uninstall. The application ID is
`io.github.addtoapplications.AddToApplications`; retain a stable ID for upgrades.

## References

- [GNOME desktop integration](https://developer.gnome.org/documentation/guidelines/maintainer/integrating.html)
- [Nautilus API](https://gnome.pages.gitlab.gnome.org/nautilus/)
- [nautilus-python](https://gitlab.gnome.org/GNOME/nautilus-python)
- [Desktop-entry Exec rules](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)
- [Gio notification lifecycle](https://docs.gtk.org/gio/method.Application.send_notification.html)
