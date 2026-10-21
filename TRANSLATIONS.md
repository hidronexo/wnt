# Translation review for every plugin revision

The English source strings and Spanish Qt catalog use the shared
`WaterNetworkTools` context. Keep algorithm IDs unchanged. Use infinitives for
actions, `Importar`/`Exportar` for file transfers, `cota` for node elevation,
and retain EPANET, PPNO, Pipe Sizer, XML and file extensions.

For 1.6 use nudos de consumo (JUNCTIONS), embalses (RESERVOIRS), depósitos
(TANKS), tuberías (PIPES), bombas (PUMPS) and válvulas (VALVES). Generic graph
nodes/edges remain nodos/aristas; generic geometry links are elementos lineales.
Distinguish cota, altura piezométrica and presión. The option inventory in
utils_epanet_options.py is included in catalog validation, despite dynamic labels.

1. Run `python translation_catalog.py --update` after changing UI text. It adds
   missing literal `tr()` strings as unfinished, preserving existing translations.
   Dynamic strings (option lists and exception messages) require explicit review;
   existing entries are retained for that reason. Never automatically translate them.
2. Review all changed names, groups, parameters and help in `wnt/i18n/wnt_es.ts`.
   Complete new translations and remove their `unfinished` attribute. Review obsolete
   strings manually, including dynamically translated strings, before removing them.
3. Run `python translation_catalog.py --check`. CI runs this without QGIS.
4. Compile with Qt `lrelease wnt/i18n/wnt_es.ts -qm wnt/i18n/wnt_es.qm`.
5. In the QGIS Python environment, run `python -m pytest -q`. The revision tests
   require the compiled catalog to match every active source catalog entry and
   exercise all registered process names and groups.
6. Run `python package_wnt.py --skip-deploy`. Packaging validates and recompiles
   translations before testing. Commit both TS and QM with the plugin changes.
7. Install the resulting ZIP in a test QGIS profile, restart QGIS and review the
   Spanish Processing panel and hydrant distance selector using metre and foot CRSs.

Release 1.4.3 also updates the contact to opensource@hidronexo.com and binds
maximum hydrant separation to the input layer CRS units.
