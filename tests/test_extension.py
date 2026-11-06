"""Exercise the real Nautilus menu objects with cached file metadata."""

import subprocess
import sys
from pathlib import Path

import gi
import pytest

gi.require_version("Nautilus", "4.1")
from gi.repository import Gio  # noqa: E402

from add_to_applications.nautilus_extension import AddToApplicationsExtension  # noqa: E402


class FileInfo:
    def __init__(self, uri, mime="application/x-executable", kind=Gio.FileType.REGULAR):
        self.location = Gio.File.new_for_uri(uri)
        self.mime = mime
        self.kind = kind

    def get_location(self):
        return self.location

    def get_file_type(self):
        return self.kind

    def get_mime_type(self):
        return self.mime

    def is_directory(self):
        return self.kind == Gio.FileType.DIRECTORY

    def is_gone(self):
        return False


@pytest.fixture
def extension(store):
    extension = AddToApplicationsExtension()
    extension.store = store
    return extension


def labels(extension, files):
    return [item.props.label for item in extension.get_file_items(files)]


def test_one_click_add_then_only_rename_and_remove(extension, script):
    source = script()
    file = FileInfo(source.as_uri(), "application/x-shellscript")
    assert labels(extension, [file]) == ["Add to Applications"]
    extension.store.add(source)
    assert labels(extension, [file]) == ["Remove from Applications", "Rename in Applications…"]
    extension.store.remove(source)
    assert labels(extension, [file]) == ["Add to Applications"]


def test_no_multi_selection_or_background_items(extension, script):
    file = FileInfo(script().as_uri())
    assert labels(extension, []) == []
    assert labels(extension, [file, file]) == []


@pytest.mark.parametrize(
    "file",
    [
        FileInfo("sftp://example.invalid/tool"),
        FileInfo("file:///tmp/picture.png", "image/png"),
        FileInfo("file:///tmp/app.desktop", "application/x-desktop"),
        FileInfo("file:///tmp/folder", kind=Gio.FileType.DIRECTORY),
        FileInfo("file:///tmp/fifo", kind=Gio.FileType.SPECIAL),
    ],
)
def test_no_action_for_unsupported_selections(extension, file):
    assert labels(extension, [file]) == []


def test_menu_does_not_open_or_sniff_selected_source(extension, tmp_path):
    # A file with cached executable metadata need not even exist to render the menu.
    file = FileInfo((tmp_path / "never-opened").as_uri())
    assert labels(extension, [file]) == ["Add to Applications"]


@pytest.mark.parametrize(
    "mime",
    [
        "text/x-python3",
        "application/x-iso9660-appimage",
        "application/vnd.appimage",
        "application/x-pie-executable",
    ],
)
def test_executable_mime_subclasses_are_supported(extension, tmp_path, mime):
    file = FileInfo((tmp_path / "program").as_uri(), mime)
    assert labels(extension, [file]) == ["Add to Applications"]


def test_import_does_not_load_gtk_into_files():
    root = Path(__file__).resolve().parents[1]
    code = (
        f"import sys;sys.path.insert(0,{str(root / 'src')!r});"
        "import add_to_applications.nautilus_extension;"
        "assert 'gi.repository.Gtk' not in sys.modules;"
        "assert 'gi.repository.Adw' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
