import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from add_to_applications import APP_ID
from add_to_applications.core import LauncherError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "tools/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_install_upgrade_uninstall_keeps_user_launchers(tmp_path):
    data = tmp_path / "data with space"
    installer.install(data)
    manifest = data / "add-to-applications/manifest.json"
    files = json.loads(manifest.read_text())["files"]
    assert len(files) >= 8
    for relative in files:
        assert (data / relative).is_file()
    desktop = data / f"applications/{APP_ID}.desktop"
    subprocess.run(["desktop-file-validate", str(desktop)], check=True)
    installer.install(data)
    unrelated = data / "applications/keep.desktop"
    unrelated.write_text("Keep me")
    installer.uninstall(data)
    assert unrelated.read_text() == "Keep me"
    assert not desktop.exists()
    assert not manifest.exists()


def test_install_refuses_unrelated_extension_file(tmp_path):
    data = tmp_path / "data"
    path = data / "nautilus-python/extensions/add_to_applications_extension.py"
    path.parent.mkdir(parents=True)
    path.write_text("Keep me")
    with pytest.raises(LauncherError, match="unrelated"):
        installer.install(data)
    assert path.read_text() == "Keep me"
    assert not (data / "add-to-applications/manifest.json").exists()


def test_modified_installation_is_not_overwritten_or_removed(tmp_path):
    data = tmp_path / "data"
    installer.install(data)
    path = data / f"applications/{APP_ID}.desktop"
    path.write_text("My edit")
    for action in (installer.install, installer.uninstall):
        with pytest.raises(LauncherError, match="modified locally"):
            action(data)
        assert path.read_text() == "My edit"
    assert (data / "add-to-applications/manifest.json").exists()


def test_manifest_path_traversal_is_rejected(tmp_path):
    data = tmp_path / "data"
    installer.install(data)
    manifest = data / "add-to-applications/manifest.json"
    content = json.loads(manifest.read_text())
    content["files"]["../../valuable"] = "checksum"
    manifest.write_text(json.dumps(content))
    with pytest.raises(LauncherError, match="invalid path"):
        installer.uninstall(data)


def test_staged_extension_is_importable_as_a_nautilus_loader_module(tmp_path):
    data = tmp_path / "data"
    installer.install(data)
    extensions = data / "nautilus-python/extensions"
    code = (
        f"import sys;sys.path.insert(0,{str(extensions)!r});"
        "import add_to_applications_extension as extension;"
        "assert extension.AddToApplicationsExtension() is not None;"
        "assert 'gi.repository.Gtk' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize("value", [[], None, "not an object", {"files": []}])
def test_malformed_manifest_is_reported_without_mutations(tmp_path, value):
    data = tmp_path / "data"
    installer.install(data)
    manifest = data / "add-to-applications/manifest.json"
    original_files = json.loads(manifest.read_text())["files"]
    manifest.write_text(json.dumps(value))
    with pytest.raises(LauncherError, match="manifest"):
        installer.uninstall(data)
    assert all((data / relative).exists() for relative in original_files)


def test_manifest_cannot_claim_an_unrelated_file_inside_data_home(tmp_path):
    data = tmp_path / "data"
    installer.install(data)
    unrelated = data / "applications/another-program.desktop"
    unrelated.write_text("Keep this unrelated launcher")
    manifest = data / "add-to-applications/manifest.json"
    content = json.loads(manifest.read_text())
    content["files"]["applications/another-program.desktop"] = hashlib.sha256(
        unrelated.read_bytes()
    ).hexdigest()
    manifest.write_text(json.dumps(content))
    with pytest.raises(LauncherError, match="invalid path"):
        installer.uninstall(data)
    assert unrelated.exists()
