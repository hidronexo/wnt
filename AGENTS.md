# WNT — agent instructions

Follow the central policy in `hidronexo-meta/AGENTS.md`.

- Visibility and license: public, `GPL-2.0-or-later` (see `repos.toml` in `hidronexo-meta`), as the QGIS plugin repository requires. Authors, commits, and public metadata use `HIDRONEXO <opensource@hidronexo.com>`.
- WNT is a QGIS plugin (`kind = "plugin"`): the UI-import check does not apply. Keep processing logic in `wnt/utils/` independent of dialogs where practical.
- Pixi is for development only. The plugin runs with the Python bundled with QGIS; tests marked `qgis` need a QGIS Python environment and are excluded from `pixi run test`.
- The version lives in `pyproject.toml` and `wnt/metadata.txt`; `pixi run release` updates both. Keep the plugin `changelog` in `metadata.txt` current by hand.
- WNT must not require private HIDRONEXO projects. It configures an external EPANET toolkit library at runtime and does not depend on `entoolkit`.
