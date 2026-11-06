import pytest

from add_to_applications.core import LauncherStore


def pytest_addoption(parser):
    parser.addoption(
        "--nautilus-loader", help="path to a nautilus-python loader for isolated tests"
    )


@pytest.fixture
def store(tmp_path):
    return LauncherStore(tmp_path / "data", tmp_path / "state")


@pytest.fixture
def script(tmp_path):
    def create(name="my_tool.sh", content=b"#!/bin/sh\nexit 0\n", executable=True):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o755 if executable else 0o644)
        return path

    return create
