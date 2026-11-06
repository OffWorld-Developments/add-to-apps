# Contributing

Preserve the one-click path: no mandatory dialog, manager window, or configuration
step when adding a file. Optional adjustments belong on the already-added file.

Use Python 3.11+ and Nautilus API 4.1. Keep GTK out of the Files process, selected
paths out of shell commands, and executable inspection free of code execution.
New functionality that changes files needs failure handling and meaningful tests.

Run `ruff check .`, `ruff format --check .`, and `python3 -m pytest -q` before sending changes. The complete
suite requires GNOME libraries, desktop-file-utils, a private D-Bus session, and
Xvfb/xauth. See README.md for dependencies. Test only with temporary XDG paths.
Packaging tests extract the actual source archive and exercise its installer and
uninstaller. See [publishing](docs/PUBLISHING.md) for release preparation.

For bug reports, include the distribution, GNOME/Files versions, extension version,
the action taken, and any helper error from the user journal. Replace private paths
before posting logs. For quoting bugs, a minimal synthetic filename is preferable
to uploading the executable.

Report suspected security issues privately to the repository owner through the
hosting platform's private vulnerability reporting feature when available. Do not
include exploit details or private executable paths in public issues.
