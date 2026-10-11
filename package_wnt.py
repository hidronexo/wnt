#!/usr/bin/env python3
"""Validate, deploy, and package the WNT QGIS plugin."""

import argparse
import configparser
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess  # nosec B404
import sys
import zipfile


class PackageError(RuntimeError):
    """Raised when the packaging environment is incomplete."""


def find_executable(names, extra_paths=()):
    """Return the first available executable from PATH or explicit locations."""
    for name in names:
        executable = shutil.which(name)
        if executable:
            return Path(executable)

    for path in extra_paths:
        candidate = Path(path).expanduser()
        if candidate.is_file():
            return candidate

    joined = ", ".join(names)
    raise PackageError(f"Required executable not found: {joined}")


def require_module(name, install_name=None):
    """Ensure a Python module is installed in the active environment."""
    if importlib.util.find_spec(name) is None:
        package = install_name or name
        raise PackageError(
            f"Python module '{name}' is not installed. "
            f"Install it with: {sys.executable} -m pip install {package}"
        )


def run_step(label, command, cwd, env):
    """Run one packaging step and stop on failure."""
    print(f"\n{label}...", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)  # nosec B603


def executable_locations():
    """Return platform-specific fallback locations for packaging tools."""
    prefix = Path(sys.prefix)
    bin_dir = prefix / ("Scripts" if os.name == "nt" else "bin")
    qt_bin_dir = prefix / ("Library/bin" if os.name == "nt" else "bin")

    pb_tool = [bin_dir / "pb_tool.exe", bin_dir / "pb_tool"]
    lrelease = [
        qt_bin_dir / "lrelease.exe",
        qt_bin_dir / "lrelease",
    ]
    return pb_tool, lrelease


def create_plugin_zip(plugin_dir, archive_path):
    """Create a QGIS plugin archive from the files declared in pb_tool.cfg."""
    config = configparser.ConfigParser(interpolation=None)
    config.read(plugin_dir / "pb_tool.cfg", encoding="utf-8")
    plugin_name = config.get("plugin", "name")
    file_options = ("python_files", "main_dialog", "compiled_ui_files", "resource_files", "extras")
    configured_files = []
    for option in file_options:
        configured_files.extend(config.get("files", option, fallback="").split())
    configured_dirs = config.get("files", "extra_dirs", fallback="").split()

    entries = []
    for relative_name in configured_files:
        source = plugin_dir / relative_name
        if not source.is_file():
            raise PackageError(f"Configured plugin file not found: {source}")
        entries.append((source, Path(plugin_name) / relative_name))
    for relative_name in configured_dirs:
        source_dir = plugin_dir / relative_name
        if not source_dir.is_dir():
            raise PackageError(f"Configured plugin directory not found: {source_dir}")
        for source in source_dir.rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            entries.append((source, Path(plugin_name) / source.relative_to(plugin_dir)))

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, archive_name in sorted(entries, key=lambda entry: entry[1].as_posix()):
            archive.write(source, archive_name.as_posix())


def parse_args(argv=None):
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help="create the ZIP without deploying the plugin to the local QGIS profile",
    )
    return parser.parse_args(argv)


def package(argv=None):
    """Run all validation and packaging steps."""
    args = parse_args(argv)
    repository = Path(__file__).resolve().parent
    plugin_dir = repository / "wnt"
    ts_file = plugin_dir / "i18n/wnt_es.ts"
    qm_file = plugin_dir / "i18n/wnt_es.qm"

    if not (plugin_dir / "pb_tool.cfg").is_file():
        raise PackageError(f"Plugin configuration not found in {plugin_dir}")
    if not ts_file.is_file():
        raise PackageError(f"Translation catalog not found: {ts_file}")

    for module in ("pytest", "bandit", "flake8", "defusedxml", "pb_tool"):
        require_module(module)

    _, lrelease_paths = executable_locations()
    pb_command = [sys.executable, "-c", "from pb_tool.pb_tool import cli; cli()"]
    lrelease = find_executable(
        ("lrelease", "lrelease-qt5", "lrelease5", "pyside6-lrelease"),
        lrelease_paths,
    )
    env = os.environ.copy()

    run_step("Checking translations",
             [sys.executable, "translation_catalog.py", "--check"], repository, env)
    run_step(
        "Compiling translations",
        [str(lrelease), str(ts_file), "-qm", str(qm_file)],
        repository,
        env,
    )
    run_step("Running pytest", [sys.executable, "-m", "pytest", "-q"], repository, env)
    run_step(
        "Running Bandit",
        [sys.executable, "-m", "bandit", "-r", "wnt", "package_wnt.py", "-x", "tests"],
        repository,
        env,
    )
    run_step(
        "Running Flake8",
        [sys.executable, "-m", "flake8", "package_wnt.py", "wnt", "tests", "--statistics", "--count"],
        repository,
        env,
    )
    run_step("Validating pb_tool configuration", pb_command + ["validate"], plugin_dir, env)

    if not args.skip_deploy:
        run_step("Deploying plugin", pb_command + ["deploy", "-y"], plugin_dir, env)

    archive_path = plugin_dir / "wnt.zip"
    print("\nCreating plugin ZIP...", flush=True)
    create_plugin_zip(plugin_dir, archive_path)
    if not archive_path.is_file():
        raise PackageError(f"Packaging did not create the expected archive: {archive_path}")

    print(f"\nPackage created: {archive_path}")
    return 0


def main():
    """CLI entry point with concise error reporting."""
    try:
        return package()
    except PackageError as error:
        print(f"ERROR: {error}", file=sys.stderr)
    except subprocess.CalledProcessError as error:
        print(f"ERROR: command failed with exit code {error.returncode}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
