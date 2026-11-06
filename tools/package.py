#!/usr/bin/env python3
"""Create a deterministic source archive and SHA-256 checksum, offline."""

import argparse
import gzip
import hashlib
import os
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from add_to_applications import VERSION  # noqa: E402

NAME = f"add-to-applications-{VERSION}"
ROOT_FILES = (
    "README.md",
    "COPYING",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "pyproject.toml",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
)
SOURCE_SUFFIXES = {".py", ".c", ".md", ".yml", ".yaml"}


def source_files():
    paths = [ROOT / name for name in ROOT_FILES]
    for directory in ("src", "tools", "tests", "docs", ".github"):
        paths.extend(
            path
            for path in (ROOT / directory).rglob("*")
            if path.suffix in SOURCE_SUFFIXES
            and "__pycache__" not in path.parts
            and (path.is_file() or path.is_symlink())
        )
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Release source must be a regular file: {path.relative_to(ROOT)}")
    return sorted(paths)


def build(output_directory: Path, tag: str | None = None) -> tuple[Path, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    if project["project"]["version"] != VERSION:
        raise ValueError("pyproject.toml and the application version do not match")
    if tag is not None and tag != f"v{VERSION}":
        raise ValueError(f"The release tag must be v{VERSION}, not {tag!r}")
    paths = source_files()
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / f"{NAME}.tar.gz"
    descriptor, temporary = tempfile.mkstemp(prefix=".source-", dir=output_directory)
    try:
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for path in paths:
                        info = archive.gettarinfo(path, arcname=f"{NAME}/{path.relative_to(ROOT)}")
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mtime = 0
                        info.mode = 0o644
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
            raw.flush()
            os.fsync(raw.fileno())
            os.fchmod(raw.fileno(), 0o644)
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    from add_to_applications.core import atomic_write

    atomic_write(
        output.with_suffix(output.suffix + ".sha256"),
        f"{checksum}  {output.name}\n".encode(),
        0o644,
    )
    return output, checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--tag", help="require a release tag matching the application version")
    args = parser.parse_args()
    try:
        output, checksum = build(args.output_dir, args.tag)
    except (OSError, ValueError) as error:
        print(f"Packaging error: {error}", file=sys.stderr)
        return 1
    print(output)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
