"""Source packs retain their branded executable through stage-and-swap."""
import json
import sys
from pathlib import Path

import pytest

from hermes_cli.main_desktop import _desktop_packaged_executable_in, _swap_staged_desktop_app


@pytest.mark.parametrize("name", ["Actelyo Law Harness", "Hermes"])
def test_branded_source_pack_is_discovered_and_promoted(tmp_path, name):
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    (desktop / "package.json").write_text(json.dumps({"productName": "Actelyo Law Harness"}), encoding="utf-8")
    staging = desktop / ".staging-test"
    relative = {
        "win32": Path("win-unpacked") / f"{name}.exe",
        "darwin": Path("mac") / f"{name}.app/Contents/MacOS/{name}",
        "linux": Path("linux-unpacked") / name,
    }[sys.platform]
    executable = staging / relative
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"packaged application")
    assert _desktop_packaged_executable_in(staging) == executable
    installed = _swap_staged_desktop_app(desktop, staging)
    assert installed == desktop / "release" / relative
    assert installed.read_bytes() == b"packaged application"
