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


def test_status_distinguishes_dependencies_from_persisted_installation(tmp_path, capsys):
    data = tmp_path / "data"
    assert not installer.installation_status(data)
    assert "Not installed" in capsys.readouterr().out
    assert not data.exists(), "Status must not create any installation files"
    installer.install(data)
    capsys.readouterr()
    assert installer.installation_status(data)
    assert "present and intact" in capsys.readouterr().out
    installer.uninstall(data)
    capsys.readouterr()
    assert not installer.installation_status(data)
    assert "Not installed" in capsys.readouterr().out


def test_status_reports_missing_and_modified_files(tmp_path, capsys):
    data = tmp_path / "data"
    installer.install(data)
    capsys.readouterr()
    entry = data / "nautilus-python/extensions/add_to_applications_extension.py"
    entry.unlink()
    runner = data / "add-to-applications/add_to_applications/runner.py"
    runner.write_text("A local edit")
    assert not installer.installation_status(data)
    output = capsys.readouterr().out
    assert "Missing: nautilus-python/extensions/add_to_applications_extension.py" in output
    assert "Modified: add-to-applications/add_to_applications/runner.py" in output
    assert runner.read_text() == "A local edit"


def test_reinstall_restores_missing_files_and_rechecks_status(tmp_path):
    data = tmp_path / "data"
    installer.install(data)
    entry = data / "nautilus-python/extensions/add_to_applications_extension.py"
    entry.unlink()
    assert not installer.installation_status(data)
    installer.install(data)
    assert installer.installation_status(data)


def test_stage_message_does_not_claim_a_normal_desktop_install(tmp_path, capsys):
    installer.install(tmp_path / "stage", staged=True)
    output = capsys.readouterr().out
    assert "Staged Add to Applications" in output
    assert "Files loads this installation" not in output
