"""Tests for the QGIS plugin packaging helpers."""

import zipfile

import pytest

from package_wnt import PackageError, create_plugin_zip


def test_create_plugin_zip_uses_configured_files_and_plugin_root(tmp_path):
    plugin_dir = tmp_path / "source"
    plugin_dir.mkdir()
    (plugin_dir / "pb_tool.cfg").write_text(
        """[plugin]
name: wnt
[files]
python_files: __init__.py
main_dialog:
compiled_ui_files:
resource_files:
extras: metadata.txt
extra_dirs: processes
""",
        encoding="utf-8",
    )
    (plugin_dir / "__init__.py").write_text("", encoding="utf-8")
    (plugin_dir / "metadata.txt").write_text("name=wnt\n", encoding="utf-8")
    processes = plugin_dir / "processes"
    processes.mkdir()
    (processes / "algorithm.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache = processes / "__pycache__"
    cache.mkdir()
    (cache / "algorithm.pyc").write_bytes(b"cache")
    archive_path = tmp_path / "wnt.zip"

    create_plugin_zip(plugin_dir, archive_path)

    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == [
            "wnt/__init__.py",
            "wnt/metadata.txt",
            "wnt/processes/algorithm.py",
        ]


def test_create_plugin_zip_rejects_missing_configured_file(tmp_path):
    plugin_dir = tmp_path / "source"
    plugin_dir.mkdir()
    (plugin_dir / "pb_tool.cfg").write_text(
        """[plugin]
name: wnt
[files]
python_files: missing.py
""",
        encoding="utf-8",
    )

    with pytest.raises(PackageError, match="Configured plugin file not found"):
        create_plugin_zip(plugin_dir, tmp_path / "wnt.zip")
