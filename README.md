# Add to Apps

**Right-click an executable in GNOME Files → Add to Applications. Done.**

Press Super and type its name to find it alongside installed apps. There is no
launcher editor, setup wizard, or background manager. A notification offers **Undo**.

Once added, the same file's context menu offers **Rename in Applications…** and
**Remove from Applications**. Removing a shortcut keeps your executable file.

## Status and compatibility

Version **0.1.0**. Targets **GNOME 51 / Files 51**, the stable series as of
November 5, 2026, using Nautilus's **4.1 extension API**. This is a Files extension,
not a GNOME Shell extension; it does not patch the overview or Shell internals.

The automated suite exercises the real nautilus-python embedded loader and C menu
ABI, Nautilus menu objects, the GLib desktop-entry parser and launcher, GTK
4/libadwaita, and notification actions through a private
D-Bus session. See [the release checklist](docs/RELEASING.md) for the additional
desktop acceptance checks required before a public stable release.
The exact completed checks and remaining acceptance work are recorded in
[local validation](docs/VALIDATION.md).

## Install

Download and extract the source archive from the repository's **Releases** page,
or clone the repository. Run the commands below from that extracted/cloned folder.

Install the runtime dependencies through your distribution, then install for your
normal user. **Do not run the installer with sudo.** It does not download anything.

On Arch Linux with GNOME 51:

```sh
sudo pacman -S --needed nautilus-python python-gobject libadwaita
python3 tools/install.py
```

On Fedora with GNOME 51:

```sh
sudo dnf install nautilus-python python3-gobject libadwaita
python3 tools/install.py
```

On Ubuntu with GNOME 51:

```sh
sudo apt install python3-nautilus python3-gi gir1.2-adw-1 gir1.2-nautilus-4.1
python3 tools/install.py
```

The installer checks for Python 3.11+, PyGObject, Nautilus 4.1, GTK 4, libadwaita,
GioUnix, and the Nautilus Python extension loader. Older GNOME releases are not a
supported target. The interface currently uses English.

Restart Files when convenient by closing its windows, running `nautilus -q`, and
opening Files again. An extension cannot be loaded into an already running Files
process. The installer deliberately does not close your windows for you.

Right-click a local Linux executable, AppImage, or script with a `#!` interpreter
line, then choose **Add to Applications**. If it is your file and lacks execute
permission, the action enables owner execute permission. Adding never runs the
program or extracts an AppImage.

## Behavior

- Names come from the filename, with common executable suffixes removed.
- A matching `.svg`/`.png`, or `icon.svg`/`icon.png` in the same folder, is used when
  present. Otherwise the standard executable icon is used. No icon is downloaded.
- Launchers start in the executable's folder, which helps portable applications
  find their neighboring resources.
- Files stay in their original location. Moving or deleting an executable or its
  sidecar icon can break its shortcut. A stable symlink is useful for versioned
  programs; the shortcut keeps the symlink path.
- Adding the same path twice is harmless. The helper also checks visible existing
  launchers for that executable before adding one; complex wrapper commands may
  not be recognized.
- Programs launch without a terminal. This first version targets graphical apps;
  interactive command-line tools that need a terminal are not supported by the UI.
- Only single-file, native selections are supported. Remote URIs, folders,
  Windows `.exe` files, and existing `.desktop` files do not get this action.
  MIME recognition is based on Files's cached content type; the helper validates
  the selected file before creating a launcher.
- Undo works from the notification for up to seven days, including after the
  helper exits. It refuses to overwrite later or external changes. Undo removes
  or restores the shortcut; it leaves any granted execute permission in place.
- There is no resident process. A short-lived helper saves the change and sends
  the notification. Rename opens one small native window.

Files must be trusted before you launch them. This extension registers shortcuts;
it does not scan, sandbox, update, or install the selected software.

## Uninstall

```sh
python3 tools/install.py --uninstall
```

Restart Files again. Existing application shortcuts remain usable, and executable
files are kept. Undo notifications require the helper, so they stop working after
uninstall. Reinstall to use the right-click rename/remove actions again.

The installer tracks its files and refuses to overwrite or delete locally modified
files or unrelated extensions. To uninstall from a custom data directory, pass
the same `--data-home /absolute/path` used for installation.

## Development

Install the runtime dependencies above plus `pytest`, `desktop-file-utils`,
D-Bus, Xvfb, xauth, a C compiler, pkg-config, and Nautilus development headers.
The compiler is only used by the loader integration test. Install Ruff for linting.
On Arch:

```sh
sudo pacman -S --needed python-pytest desktop-file-utils dbus xorg-server-xvfb xorg-xauth ruff base-devel
ruff check .
python3 -m pytest -q
```

Tests use temporary XDG data/state/config/cache/runtime directories. The notification
and UI tests start private D-Bus sessions and a headless display, so they do not
add launchers to your application menu or send notifications to your desktop.
Tests require permission to create local sockets.

Stage an install without changing your desktop:

```sh
python3 tools/install.py --stage --data-home /tmp/add-to-applications-stage
```

See [architecture](docs/ARCHITECTURE.md), [contribution guidelines](CONTRIBUTING.md),
and [release checks](docs/RELEASING.md). Licensed under
[GPL-3.0-or-later](COPYING).

## Distribution

This project adds an action to GNOME Files. It is distributed through repository
releases, not extensions.gnome.org, which hosts GNOME Shell extensions. A Shell
integration would be a separate component with its own interface and tests.

See [publishing](docs/PUBLISHING.md) for repository setup, release artifacts, and
the distinction between Files and Shell extension distribution.

[Repository](https://github.com/OffWorld-Developments/add-to-apps) ·
[Releases](https://github.com/OffWorld-Developments/add-to-apps/releases) ·
[Report a bug](https://github.com/OffWorld-Developments/add-to-apps/issues)

The installed Python package, application ID and `add-to-applications-*` launcher
files retain their original names so existing installations remain compatible.
