# Release checklist

0.1.0 is an initial release candidate until all acceptance checks below pass.
Passing automated tests alone is not a claim of desktop certification.

## Automated gates

- `ruff check .`
- `ruff format --check .`
- `python3 -m pytest -q` with all integration tests enabled, no skips.
- Validate an isolated staged install and uninstall.
- Build a source archive with `python3 tools/package.py`; check its checksum.
- Confirm README compatibility, version, changelog, license, and dependency names.

CI uses an up-to-date Arch Linux GNOME stack to catch changes in the latest stable
desktop. Review upstream version changes before expanding the support statement.

## Real desktop acceptance on GNOME 51

Use a disposable account or VM with the latest stable Files and nautilus-python.

1. Install, restart Files, and right-click an unregistered graphical ELF executable.
   Confirm **Add to Applications** appears directly in the menu without a submenu.
2. Click once. Confirm there is no dialog, the notification includes **Undo**, and
   Super search and the app grid show the new app without restarting Shell.
3. Launch it, including an app that loads resources relative to its folder.
4. Repeat with an AppImage and a shebang script. Check names, sidecar icons, and
   automatic owner execute permission on a non-executable owned file.
5. Confirm the file menu now offers rename/remove; test keyboard-only interaction,
   screen-reader labels, long names, HiDPI, and light/dark appearance for rename.
6. Remove the shortcut. Confirm it disappears from search and the file remains.
7. Test notification Undo for add, rename, and remove after the helper exits and
   after logging out/back in where the desktop retains the notification.
8. Verify stale Undo cannot replace a later change or an externally edited entry.
9. Verify selections of images, folders, desktop files, remote files, and multiple
   files offer no action. Verify an already-registered app does not get duplicated.
10. Uninstall/reinstall. Confirm other extensions and existing shortcuts still work.
    Check user journal output for tracebacks, critical warnings, or stale processes.

Record the exact distribution, Files, GNOME Shell, nautilus-python, GTK and
libadwaita versions and acceptance date in the release notes. Do not claim tests on
distributions that have not actually been exercised.

## Publication

- Choose the public repository owner and confirm the application ID before the
  first stable release. It is currently a project namespace, not a claim of an
  existing GitHub organization or GNOME endorsement.
- Enable private vulnerability reporting and name the actual maintainer(s).
- Tag only after the gates pass. Attach the source archive and SHA-256 checksum.
- Publishing or uploading is a separate action; the packaging script is offline.

See [publishing](PUBLISHING.md) for the repository setup, tag validation, CI build
artifacts, and release draft. The Files extension is not an extensions.gnome.org
submission; that site requires a separately implemented Shell integration.
