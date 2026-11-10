"""Native admission must inspect long cache paths without relaxing containment."""
import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from pm.filesystem import extended_path
from pm.store import tree_digest
from scripts.bundles.native_prepared import _check_links, _owned


@pytest.mark.platforms("windows")
def test_link_inspection_reaches_cache_files_beyond_classic_windows_limit(tmp_path, monkeypatch):
    folder = extended_path(tmp_path) / "site-packages" / "elevenlabs" / "__pycache__"
    folder.mkdir(parents=True)
    cache = folder / ("workspace_access_" * 9 + ".cpython-314.pyc")
    cache.write_bytes(b"cache")
    assert len(str(cache).removeprefix("\\\\?\\")) > 260
    real_lstat = Path.lstat
    inspected = []

    def classic_lstat(path, *args, **kwargs):
        if len(str(path)) > 260:
            assert str(path).startswith("\\\\?\\"), "long path reached Win32 without extended spelling"
            inspected.append(path)
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", classic_lstat)
    _check_links(tmp_path, tmp_path)
    assert cache in inspected


@pytest.mark.platforms("windows")
def test_tree_digest_reads_long_files_and_preserves_logical_relative_names(tmp_path):
    relative = Path("package_" + "x" * 120) / ("entry_" + "y" * 120 + ".bin")
    file = extended_path(tmp_path) / relative
    file.parent.mkdir(parents=True)
    file.write_bytes(b"verified payload bytes")
    assert len(str(file).removeprefix("\\\\?\\")) > 260
    expected = hashlib.sha256(relative.as_posix().encode() + b"\0verified payload bytes").hexdigest()
    assert tree_digest(tmp_path) == expected


def test_link_escape_is_still_rejected(tmp_path):
    root = tmp_path / "payload"
    outside = tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    link = root / "escape"
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escaped"):
        _check_links(root, root)
    with pytest.raises(ValueError, match="escaped"):
        _owned(Path("relative"), root)
