# Local validation — November 5, 2026

The implementation passed **77 tests** with no skips. Ruff lint and formatting
checks passed. Source staging, upgrade, conservative uninstall, desktop-file
validation, and deterministic archive creation were also checked.

Environment:

| Component | Version |
| --- | --- |
| Distribution | Arch Linux |
| GNOME Shell / Files | 51.1 |
| Nautilus extension library | 51.1-1, API 4.1 |
| nautilus-python | 4.2.0-1, official Arch package |
| Python | 3.14.9 |
| PyGObject | 3.58.1 |
| GTK | 4.24.1 |
| libadwaita | 1.10.0 |
| desktop-file-utils | 0.28 |
| Ruff | 0.17.4 |

The host's Python loader was not installed and sudo required a password. For the
loader integration test, the official package was downloaded and its library
extracted to a temporary directory. No system package or active desktop extension
was installed by this validation.

The C integration probe loads the genuine nautilus-python shared library, lets it
initialize embedded Python and discover the staged extension, instantiates its C
menu-provider type, supplies cached file metadata through Nautilus's FileInfo ABI,
and activates the actual Add/Remove menu signals. This validates the embedding and
helper subprocess path independently of a plain Python import.

The notification probe verifies delivery to a private notification service, helper
exit, cold D-Bus activation of the Undo button, and restoration of the previous
launcher state. The GTK probe opens the real rename window on an isolated Xvfb
display, checks name validation, and saves a rename. Desktop launch tests execute
only synthetic programs and verify literal argv and working directories for
spaces, quotes, shell metacharacters, Unicode, percent signs, and equals signs.

Reproduce a temporary-loader run with:

```sh
python3 -m pytest -q --nautilus-loader=/absolute/path/to/libnautilus-python.so
```

With the system loader installed, use `python3 -m pytest -q` instead. The loader
test requires a C compiler, pkg-config, and Nautilus development headers.

## Remaining acceptance work

On November 6, 2026, the owner reported testing the functionality on their GNOME
desktop and confirmed that it behaved as expected. This provides interactive
acceptance alongside the isolated automated checks.

The detailed checklist in [RELEASING.md](RELEASING.md) remains available for recording
specific distribution, AppImage, accessibility, HiDPI and session-restoration
coverage. Those individual scenarios have not been separately logged here.
No Fedora/Ubuntu runtime test or hosted CI run is claimed.

## Repository preparation — November 6, 2026

The expanded suite passed **85 tests** with no skips using the installed
nautilus-python 4.2.0 loader. Ruff lint and formatting checks passed. The additional
checks cover malformed installation manifests, protection of unrelated files,
reproducible release archives, tag/version agreement, source symlink rejection,
and install/uninstall from the extracted release archive.

Repository issue forms, contribution templates, release notes, and CI artifact
collection are prepared. Local Git metadata is initialized on `main`; no remote
or hosted workflow run is recorded in this validation.

Treat this as a release candidate until those checks pass and the repository's
actual maintainer and private security-reporting channel are configured.
