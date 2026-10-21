# WNT 1.6.0 implementation and verification plan

Status: implementation and release verification completed on 2026-10-21 in the
authorized wnt-1.6.0 worktree, branch dev. Publication status is recorded separately
in Git; this plan is not a substitute for checking the remote branch.

## 1. Scope and release constraints

- Deliver version 1.6.0, with six explicit EPANET layer categories: JUNCTIONS,
  RESERVOIRS, TANKS, PIPES, PUMPS and VALVES.
- Implement conditional parameter widgets, preserve advanced options, coordinate
  English/Spanish text, and fix the data-preservation problems below.
- Keep algorithm IDs stable. Migrate parameter IDs deliberately: changing a
  Python constant alone does not migrate saved Processing models or scripts.
- User-authorized publication target: `dev`, after successful checks; never publish to master.
  Inspect repository provenance first: the current checkout reports the project
  files as untracked. Preserve all existing work and establish a reviewable baseline.
- Keep version 1.6.0 in pyproject.toml and wnt/metadata.txt. Do not blindly run a
  version bump that advances an already prepared 1.6.0 to 1.6.1.
- Final delivery: tested plugin ZIP, checksum, changelog and explicit validation
  report. Publication, commit and push are separate release actions.

## 2. Corrections to the preceding review

1. PipeSizing's FIELD_FIRE_FLOW selects a flow-setting NAME, not a numeric flow.
   FIRE_FLOW remains necessary when that field is selected. Disable both controls
   only when there is no fire-scenario layer; never make them mutually exclusive.
2. Network from lines retains line types through LINK_TYPE_FIELD and line_types.
   Its entire output cannot be renamed PIPES without categorizing the features.
3. Results from EPANET currently creates attribute tables, not spatial network
   layers. Category-specific result tables need stable ID/time keys; adding
   geometry is a separate feature, not an implicit part of this migration.
4. A reservoir head is not terrain elevation. DEM/TIN tools must not silently
   overwrite the reservoir hydraulic boundary value with sampled terrain.
5. CHECKFREQ, MAXCHECK and DAMPLIMIT must not be assumed exclusive to 2.2.
   Build a version capability matrix; HEADERROR and FLOWCHANGE are currently
   emitted unconditionally even for the 2.00.12 selection.

## 3. Confirmed source findings and required fixes

| Priority | Evidence | Finding and action |
| --- | --- | --- |
| P0 | wnt/processes/wnt_network_to_epanet.py, processAlgorithm | New WntNode/WntLink objects are populated with identity, type, geometry and limited elevation/length data. Map all supported hydraulic properties and domain attributes explicitly; verify demands, diameters, roughness, tank data, pump curves/power and valve settings survive export. |
| P0 | Same file, pipe construction | Pipes are assigned PIPE regardless of a CVPIPE subtype. Preserve check-valve semantics and test them explicitly. |
| P0 | wnt/processes/wnt_network_from_epanet.py | Import still merges three point categories and three line categories into two outputs. Split by actual type without losing attributes or geometry. |
| P1 | wnt/processes/wnt_network_to_epanet.py, template serialization | HEADERROR/FLOWCHANGE are unconditional; CHECKFREQ/MAXCHECK/DAMPLIMIT are gated on 2.2. Correct capabilities against official documentation and actual supported toolkit versions. |
| P1 | wnt/processes/wnt_pipe_properties_to_epanet_scenario.py | Requires type and filters only PIPE/CVPIPE. Use the PIPES category contract without requiring a public CVPIPE subtype; include check-valve pipes and preserve their status. |
| P1 | wnt/processes/wnt_network_to_pipesizing.py | Selected pressure/series/flow-name fields are read but required-field checks principally cover IDs and hydrant endpoints. Validate every selected field, report its layer, and reconcile optional fire-pressure fallback with the form contract. |
| P1 | Same file, fire-scenario serialization | Setting names pass through _flow_setting_name while scenario rows use the original flow_name. Verify normalization parity; serialize the same canonical token in both places. |
| P1 | wnt/processes/wnt_network_from_lines.py | Generated line types are retained but output is named _links. Split outputs by category and reject unsupported types explicitly. |
| P1 | README.md and wnt/i18n/wnt_es.ts | README describes two-layer INP export; Spanish contains 'Links de salida' and 'Capa de conexiones' for Junctions. Coordinate terminology, help and catalog tests. |

Additional checks during implementation, not yet confirmed runtime defects:
missing/empty sources, null/non-finite numbers, invalid geometries, duplicate IDs
across categories, missing endpoint IDs, invalid pump/valve subtypes, undefined
patterns/curves/trace nodes, whitespace in identifiers/file paths, cancellation,
sink write failures and partial output files. Validate before writing final files.
Use atomic replacement for file exports where feasible.

## 4. Shared layer contract and compatibility

Create a QGIS-independent category/schema registry in wnt/utils, with adapters
in Processing. Define required fields, optional properties, defaults, aliases,
subtypes and serialization rules once. Keep internal nodes()/links() graph APIs
and official INP REPORT NODES/LINKS keywords.

- JUNCTIONS: elevation, base/multiple demands, patterns, emitters and quality.
- RESERVOIRS: total head, head pattern and quality; distinguish head from terrain.
- TANKS: bottom elevation, levels, diameter, minimum volume, volume curve,
  mixing, quality and reactions where supported.
- PIPES: endpoints, length, diameter, roughness, minor loss, status/CV semantics,
  vertices and reactions.
- PUMPS: endpoints, power/head curve, speed, pattern, status and energy data.
- VALVES: endpoints, diameter, subtype, setting, minor loss and status.

### Accepted check-valve representation (2026-10-21)

CVPIPE is an internal representation only. The public PIPES layer uses a
`status` field with OPEN, CLOSED or CV; it does not expose CVPIPE as a separate
category or selectable type. Check-valve pipes remain in PIPES, never VALVES.

- Layer adapter: `status = CV` creates the internal CVPIPE representation.
- Reverse adapter: internal CVPIPE becomes a PIPES feature with `status = CV`.
- INP serialization: write CV in the Status column of [PIPES]. Preserve endpoint
  order, which defines the permitted flow direction.
- Legacy input adapter: accept `type = CVPIPE` and normalize it to the public
  status contract. Reject contradictory explicit states rather than silently
  discard the check valve.
- Scenario exporters process all PIPES, including CV, without requiring a
  public `type` field. Forms, help and translations describe check-valve status;
  CVPIPE appears only in internal code or legacy-migration documentation.
- Acceptance test: INP CV -> PIPES/status CV -> internal CVPIPE -> INP CV,
  preserving endpoints and hydraulic properties. Also test legacy normalization
  and conflicting type/status input.

Maintain the two global ID namespaces (point objects and line objects). Preserve
references and distinguish an absent optional layer from an empty valid layer.
Do not require all six categories to contain features.

Provide an explicit adapter for legacy two-layer inputs. Preserve existing
algorithm IDs; define old-to-new parameter mappings and conflict rules (prefer
new explicit parameter, reject contradictory simultaneous inputs). Document
output migration, which cannot be solved by input aliases. Never create hidden
duplicate physical outputs merely to preserve old names.

## 5. Inventory of all 24 algorithms

| Algorithm | Planned 1.6 change |
| --- | --- |
| Network from EPANET | Six typed outputs, complete properties and subtype preservation. |
| Network to EPANET | Six inputs; INPUT_JUNCTIONS/INPUT_PIPES canonical names; complete serialization and existing-model preservation. |
| Results from EPANET | Category-specific hydraulic/quality tables; retain ID/time and joinability; activate only relevant result destinations. |
| Demand to EPANET scenario | JUNCTIONS input; validate demands and IDs. |
| Pipe properties to EPANET scenario | PIPES input, including status CV; validate numeric diameter/roughness without exposing internal CVPIPE. |
| Assign demand | JUNCTIONS target in EPANET workflow; preserve source/assignment semantics. |
| Update assignment | Coordinate target naming with Assign demand; preserve assignment geometry and identity. |
| Network to PPNO | JUNCTIONS pressure constraints and PIPES groups; verify references against the selected INP. |
| Network to PipeSizing | JUNCTIONS pressure constraints and PIPES series; fire controls as corrected above. |
| Network from lines | JUNCTIONS plus categorized PIPES/PUMPS/VALVES; default PIPE only when no type supplied; preserve source fields. |
| Classify | Compute topology with PIPES/PUMPS/VALVES; distribute classification to each category, preserving identity; new/update output mode. |
| Node degrees | All point and line categories; return degrees to the three point categories; new/update mode. |
| Validate | Validate the combined graph across six categories, report category/ID and preserve categorized audited outputs. |
| Network to graph | Six category inputs combined internally as graph vertices/edges. |
| Merge networks | Two categorized networks; preserve type/properties, globally consistent ID remapping and all dependent references. Do not automatically coalesce different hydraulic node types merely by proximity. |
| Network to XML | Typed EPANET adapter; preserve generic WNT/SWMM/LandXML mode and schema compatibility. |
| Network from XML | Detect format/model; split EPANET types; preserve separate generic non-EPANET route. Dynamic network/version selectors. |
| Network from LandXML | Dynamic network selector; classify only when semantics support it. A water network alone does not prove all six EPANET types or properties. |
| Elevation from DEM | One point layer and explicit target field; preserve category; distinguish terrain, tank-bottom elevation and reservoir head. |
| Elevation from TIN | Same elevation policy; dependent LandXML surface selector. |
| Split lines at points | Keep generic points/lines workflow; EPANET mode must prevent splitting pumps/valves and must preserve pipe topology/properties. Lock incompatible output CRS in update mode. |
| Connect by distance | Keep generic source/target/connection semantics; generated connection lines are not automatically hydraulic PIPES. |
| Hydrant pairs | Keep HYDRANTS/PAIRS semantics; verify generated IDs match fire-scenario consumers. |
| Configure EPANET toolkit | Preserve configuration role; verify reported toolkit version/capabilities used by export validation. |

## 6. Widgets and parameter dependencies

Implement reusable dependency rules rather than one bespoke dialog per algorithm.
Keep disabled controls visible with an explanation and retain entered values.
Advanced flags and conditional enablement are independent: analysis settings
remain under advanced options. All six network layer selectors remain accessible.
Validate rules in the algorithm too: batch, modeler and Python bypass GUI widgets.

| Controller | Dependent behavior |
| --- | --- |
| INP workflow | Existing model enables input INP and disables new-model analysis options; scratch reverses this. Network category inputs remain available in both. |
| EPANET version | Apply verified capability matrix, including demand model/pressure parameters and convergence criteria. |
| Quality type | Chemical enables chemical name, mass units, diffusion and reactions; Trace enables node selector; None disables quality controls. Verify tolerance applicability for AGE/TRACE against engine units before encoding rules. |
| Simulation duration | For zero-duration runs disable irrelevant extended-period controls without losing stored values; verify toolkit behavior. |
| Result type | Hydraulic, quality or both selects corresponding category destinations. |
| Elevation source | DEM enables raster; LandXML enables file/surface; line Z or none disables external sources. |
| Output mode | Classify, Node degrees, Elevation DEM/TIN, Split lines and Validate disable new destinations in update mode. |
| XML output format | WNT model type only for WNT XML; LandXML network type only for LandXML. |
| XML input | Populate network names; enable/populate version only for applicable WNT XML. |
| LandXML file | Populate surface/network choices after successful parsing; empty or unreadable files show a reason, clear stale choices and cannot leave invalid selections accepted. |
| Fire scenario layer | Enable flow-name field AND numeric flow value when present; disable both when absent. |

Trace-node and energy-pattern selectors should use known IDs where available;
do not invent a pattern definition from a reference. Define how pattern/curve
definitions enter a scratch model before accepting references to them.
Use safe XML parsing, bounded refresh/debounce and avoid parsing large files on
every keystroke. Retain working QGIS file-selector signal handling in widgets.py.

## 7. EPANET parameter coverage

Maintain a machine-readable inventory: UI key, English label, Spanish label,
family, default, range, units, dependency, version and INP directive.
Compare every supported option against the official EPANET 2.2 manual.

- Emitters: exponent; category-specific emitter coefficients.
- Energy: global price, optional price pattern, global pump efficiency, demand
  charge; per-pump overrides where supported by the layer schema.
- Quality: analysis type, chemical name, mass units, relative diffusivity,
  trace node and transport tolerance. Reactions subfamily: bulk/wall/tank orders,
  global and local coefficients, limiting concentration and roughness correlation.
- Calculation stability/hydraulics: trials, hydraulic accuracy, head error,
  flow change, unbalanced action/continuation, status checks, damping; expose or
  explicitly document fixed headloss formula, demand model and pressure settings.
- Times: duration, hydraulic/quality/rule/pattern/report steps, pattern/report
  start, clock time and statistic. Validate syntax, units and relationships.
- Report: status, summary, energy, node/link selection, file and page size;
  document unsupported field-level reporting options rather than claim completeness.

Keep hydraulic convergence tolerance distinct from water-quality tolerance.
Do not silently clamp invalid values or silently substitute QUALITY NONE for an
invalid requested trace analysis.

## 8. Coordinated English/Spanish terminology

Proposed glossary, applied to labels, help, logs, README and tests:

| Canonical identifier | Spanish UI |
| --- | --- |
| JUNCTIONS | Nudos de consumo (JUNCTIONS) |
| RESERVOIRS | Embalses (RESERVOIRS) |
| TANKS | Depósitos (TANKS) |
| PIPES | Tuberías (PIPES) |
| PUMPS | Bombas (PUMPS) |
| VALVES | Válvulas (VALVES) |
| Generic graph nodes / edges | Nodos / aristas del grafo |
| Elevation / head / pressure | Cota / altura piezométrica / presión |

Use 'nudos de consumo' as a category label without implying every junction has
positive demand. Preserve canonical uppercase identifiers and INP keywords.
Avoid 'conexiones' for JUNCTIONS and untranslated 'links' for PIPES. Keep generic
geometry and assignment vocabulary separate. Actions use infinitives as required
by TRANSLATIONS.md. Include units in price, demand charge, tolerances and reaction
coefficients; distinguish global pump efficiency from a curve.

Follow TRANSLATIONS.md: update TS, review every new/dynamic string, check the
catalog, compile QM and compare compiled translations against active TS entries.
Review the shared WaterNetworkTools context for ambiguous repeated source text.
No automatic translations or removal of dynamically used entries. Test the
installed ZIP in English and Spanish, including errors, tooltips and advanced
groups. Inspect accents and placeholders, not only unfinished-entry counts.

## 9. Implementation sequence and acceptance gates

1. Baseline and branch: confirm source provenance, record current test/lint/type
   results and catalog status. Existing failures remain distinguishable from regressions.
2. Registry and adapters: schemas, ID namespaces, legacy migration and property
   mapping; fixtures containing all six categories and CVPIPE/valve subtypes.
3. Import/export correctness: round-trip fixture through INP -> six layers ->
   INP; compare hydraulic properties and references, not text ordering alone.
   Test adding to an existing INP preserves unrelated sections and settings.
4. Specialized exporters and builders: scenarios, PPNO, PipeSizing, demand,
   from-lines and elevation semantics.
5. Graph and XML migration: six-category connectivity, multiple networks and
   non-EPANET compatibility; verify cycles traversing a pump or valve and node
   degrees including all line categories. Preserve categories in update mode.
6. Widgets: dependency transitions in both directions, initial/restored state,
   empty files/layers, batch/modeler execution, advanced groups and cancellation.
7. Translation/doc coordination after each phase, then full English/Spanish UI review.
8. Release verification: pixi test/lint/typecheck; QGIS-marked tests under QGIS
   Python; official toolkit parse/run checks for representative 2.2 models and
   parsing checks for claimed legacy support. Record exact environments and skips.
9. Package with package_wnt.py --skip-deploy after inspecting its prerequisites.
   Verify ZIP CRC, root layout, 1.6.0 metadata, TS/QM parity and absence of caches/
   temporary packaging trees. Install in a clean QGIS profile and confirm all
   24 algorithms load, six selectors/outputs are visible and widgets work.

Release blockers: lost hydraulic data, misclassified elements, unresolved IDs,
incorrect version directives, missing layer selectors, inactive/stale widgets,
TS/QM mismatch or an unverified packaged plugin presented as tested.

## 10. References and evidence boundaries

- Local sources: wnt/processes, wnt/utils, wnt/wnt_provider.py,
  tests/test_process_algorithms.py, tests/test_processing_metadata.py,
  tests/test_translations.py, TRANSLATIONS.md and README.md.
- Official EPA manual: https://usepa.github.io/EPANET2.2/8_analyzing_network.html
- EPA reference writer/version handling:
  https://github.com/USEPA/WNTR/blob/main/wntr/epanet/io.py
- The initial plan was a static inspection. The implementation and measured
  acceptance evidence are recorded in section 12 below.

## 11. Updated external format contracts (2026-10-21)

Source review targets: Pipe Sizer 0.1.1 at remote commit 34cf11f and PPNO 0.3.3
at 0d1b199. These are reviewed revisions, not a claim about published releases.
Do not copy private application code into this public plugin or add runtime
dependencies on either application. Use independently implemented format adapters.

- Pipe Sizer: `.pro` project and `.psr` catalog, exactly three catalog columns
  (series, diameter, roughness), semicolon comments and UTF-8 BOM handling.
  Support paths with spaces. Expose reset_initial. Replace arbitrary FLOW_ names
  with supported fire_flow_1/fire_flow_2 settings and compatible scenario tokens.
  Distinguish steady-state fire sizing from extended-period simulation: disable
  fire-specific controls when the selected INP duration is positive and explain
  which demand factors the consumer actually applies.
- PPNO: `.ext` and `.cat`, with four catalog columns (group, diameter, roughness,
  price). Preserve zero pressure constraints; validate group membership, finite
  numeric values and selected INP IDs/types. Stage project/catalog writes and
  prevent input/output collisions. Keep algorithm selection optional.
- Both exporters accept JUNCTIONS and PIPES (including status CV); retain pumps,
  valves and source/storage nodes in the referenced INP. Coordinate product
  names, units, catalog filters, error messages and help in English and Spanish.
- Acceptance: parse representative outputs using the reviewed consumer parsers
  when available, exercise zero pressure, CV, paths with spaces, BOM, invalid
  catalog columns, fire type aliases and steady/extended-period cases. Keep any
  private-code validation outside the distributable plugin and public fixtures.

Initial plan-copy baseline: 53 passed / 23 skipped. The authorized advanced
worktree had a separate 57-passed non-QGIS baseline before this implementation.

## 12. Implementation and acceptance record

- Implemented six-category INP import/export, explicit legacy input adapters,
  internal CVPIPE/public status CV, multiple demand categories, existing-model
  sparse updates and validated pattern/curve/trace references.
- Added the analysis inventory and advanced family labels, workflow/version/
  quality/duration/result/output dependencies, file-driven XML choices and
  corrected LandXML TIN namespace, CRS and narrow-triangle handling.
- Adapted builder, graph, merging, WNT XML and result tables. Generic non-EPANET
  geometry operations remain generic. Added terrain-head and pump/valve split
  safeguards. Multi-layer edits stay in undoable QGIS buffers for user saving.
- Updated Pipe Sizer and PPNO contracts, catalog validation, finite values,
  zero pressure, source INP categories, paired staged publication and cancellation.
- Replaced dormant old two-output/JSON-contract tests with active category,
  legacy adapter, missing-coordinate and round-trip regression tests.
- QGIS 3.44.11 Python with an external EPANET toolkit: **204 passed**, zero
  skipped. Thirteen warnings concern QGIS' announced EnumWidgetWrapper removal
  in QGIS 4; the tested target is QGIS 3.44, not QGIS 4.
- Pixi non-QGIS run: **70 passed / 23 skipped**, including optional native-engine
  and QGIS cases. Flake8 and mypy pass. Packaging environment: existing Conda
  wnt Python 3.12.13, used for its installed Qt/compiler/packaging tools only.
  Bandit reports zero findings; pb_tool configuration passes.
- External engine acceptance exercises none/chemical/age/trace quality with
  energy, reactions, times, reports and convergence options. The local Pipe Sizer
  consumer reports no validation errors on generated .pro/.psr; the PPNO reader
  accepts both pressure rows including zero. No consumer code is distributed.
- ZIP verification uses an extracted package and isolated temporary QGIS profile:
  CRC/layout/1.6.0 metadata, 24 algorithms, six non-advanced selectors, all listed
  advanced parameters and English/Spanish dialogs pass. TS/QM has 274 completed
  translations, no unfinished entries.

Scope boundaries: EPANET 2.0 capability serialization is unit-tested, not run
against a separate 2.0 binary. QGIS 3.38 and QGIS 4 were not exercised. Report
field filters/precision and editing new controls/rules are not form features;
existing sections are retained. The INP exporter is not a reversible text editor.
Trace/pattern IDs remain editable fields validated against the model/definitions,
not a dedicated model-browser widget. No user QGIS installation was replaced.
