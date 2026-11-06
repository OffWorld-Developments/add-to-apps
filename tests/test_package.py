"""Verify the release a downloader actually receives."""

import hashlib
import importlib.util
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("packager", ROOT / "tools/package.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def test_release_is_reproducible_and_installable_from_its_archive(tmp_path):
    archive, checksum = packager.build(tmp_path / "first", "v0.1.0")
    second, checksum_again = packager.build(tmp_path / "second", "v0.1.0")
    assert checksum == checksum_again == hashlib.sha256(second.read_bytes()).hexdigest()
    assert archive.read_bytes() == second.read_bytes()
    assert archive.with_suffix(".gz.sha256").read_text() == f"{checksum}  {archive.name}\n"
    with tarfile.open(archive) as handle:
        members = handle.getmembers()
        assert all(member.isfile() for member in members)
        assert all(".." not in Path(member.name).parts for member in members)
        assert all(
            not {"__pycache__", ".git", ".env", "dist"} & set(Path(m.name).parts) for m in members
        )
        handle.extractall(tmp_path / "extracted", filter="data")
    source = tmp_path / "extracted/add-to-applications-0.1.0"
    for required in (
        "COPYING",
        "README.md",
        ".gitignore",
        ".github/workflows/ci.yml",
        "docs/PUBLISHING.md",
        "docs/releases/v0.1.0.md",
    ):
        assert (source / required).is_file()
    data = tmp_path / "installed"
    for arguments in (["--stage"], ["--uninstall"]):
        subprocess.run(
            [
                sys.executable,
                str(source / "tools/install.py"),
                "--data-home",
                str(data),
                *arguments,
            ],
            check=True,
        )
    assert not list((data / "applications").glob("*.desktop"))


def test_mismatched_release_tag_fails_before_creating_artifacts(tmp_path):
    with pytest.raises(ValueError, match="release tag"):
        packager.build(tmp_path / "output", "v9.9.9")
    assert not (tmp_path / "output").exists()


def test_release_refuses_source_symlinks(tmp_path, monkeypatch):
    source = tmp_path / "fake-source"
    source.mkdir()
    (source / "README.md").symlink_to(ROOT / "README.md")
    monkeypatch.setattr(packager, "ROOT", source)
    with pytest.raises(ValueError, match="regular file"):
        packager.source_files()
