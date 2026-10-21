<p align="center"><img src="wnt/resources/wnt.png" width="345" height="293" title="WNT Logo"></p>

# Water Network Tools (WNT)

Water Network Tools is a QGIS Processing plugin for creating, editing, validating, importing and exporting pressurized water network data. It works with six EPANET layer categories and generic WNT node/link layers, EPANET `.inp` model files, EPANET scenario files, WNT XML, LandXML 1.2 pipe networks, LandXML TIN surfaces and pipe-sizing inputs.

Requires QGIS 3.38 or later.

## Recipes

Each bullet below is a WNT Processing algorithm. The text after the algorithm name summarizes the workflow it covers.

### Build

Available process:

- `Network from lines` - Builds EPANET-style node and link layers from CAD/GIS line features. It supports multipart lines, endpoint merging by tolerance, node elevations from zero values, line Z values, DEM rasters or one selected LandXML TIN surface, and optional node degree/topology fields.

### Demand

Available processes:

- `Assign demand` - Assigns one or more demand fields from source features to the nearest network nodes and creates assignment lines.
- `Connect by distance` - Connects source and target features by nearest distance, with optional limits for number of connections and maximum distance.
- `Update assignment` - Recalculates demand assignments after manually editing assignment lines.

### Export

Available processes:

- `Export EPANET model to INP file` - Writes an EPANET model from six typed junction, reservoir, tank, pipe, pump and valve layers. It can update an existing `.inp` while preserving its other sections, or create a new EPANET 2.0/2.2 model with editable hydraulic options.
- `Demand to epanet scenario file (.scn)` - Writes an EPANET demand scenario from a selected node demand field.
- `Pipe properties to EPANET scenario file (.scn)` - Writes an EPANET pipe scenario with diameter and roughness values for pipe links.
- `Network to XML` - Writes WNT Network XML with versioned network data and preserved EPANET, SWMM, LandXML and custom property domains, or writes a LandXML 1.2 pipe-network file.
- `Network to Pipe Sizer data file (.pro)` - Writes Pipe Sizer input data with `[SETTINGS]`, `[PRESSURES]`, `[FIRE_SCENARIOS]` and `[PIPES]` sections, including peak/fire factors, required pressures and optional hydrant-pair fire scenarios.
- `Network to pressure pipe optimization data file (.ext)` - Writes PPNO (`Pressurized Pipe Network Optimizer`) input data from network layers, an EPANET `.inp` model and a pipe catalog `.cat` file. See https://github.com/hidronexo/ppno.

### Fire

Available process:

- `Hydrant pairs` - Generates hydrant pairs/calculation scenarios from a hydrant layer, excluding pairs farther apart than the maximum separation. The output can be used by the Pipe Sizer `.pro` exporter as fire scenarios.

### Graph

Available processes:

- `Classify` - Classifies links as branched or meshed and assigns a globally unique `zone`.
- `Node degrees` - Calculates the graph degree of each network node.
- `Network to graph file` - Exports the network topology to Trivial Graph Format (TGF).
- `Validate` - Reports orphan nodes, duplicate nodes, duplicate links, links with undefined endpoints and loops.

### Import

Available processes:

- `Configure EPANET lib` - Sets the EPANET toolkit library path used by EPANET result imports.
  Configure only a trusted EPANET 2 toolkit library installed on your system.
- `Import EPANET model from INP` - Imports EPANET `.inp` files as six typed layers grouped under the model name. Every layer records the source INP and EPANET version; no generic JSON property field is used.
- `Network from LandXML file` - Imports one or more LandXML 1.2 pressure, sanitary or storm pipe networks as WNT node and link layers, preserving the declared coordinate reference system when available.
- `Results from EPANET` - Imports hydraulic results, quality results or both from EPANET simulations.
- `Network from XML` - Imports WNT Network XML files, including selected network versions, or imports LandXML 1.2 pipe networks as WNT node and link layers.

### Modify

Available processes:

- `Node elevation from DEM` - Adds or updates node elevations from a DEM raster.
- `Node elevation from TIN (LandXML)` - Adds or updates node elevations from one selected LandXML TIN surface.
- `Split lines at points` - Splits line features at point positions.
- `Merge networks` - Merges two networks and validates the final graph before creating output layers.

## Packaging

Run from an activated development environment:

```bash
python package_wnt.py
```

HIDRONEXO (opensource@hidronexo.com)

===

# Water Network Tools (WNT)

Water Network Tools es un plugin de QGIS Processing para crear, editar, validar, importar y exportar datos de redes de agua a presión. Trabaja con capas WNT de nodos y elementos lineales, archivos de modelo EPANET `.inp`, archivos de escenario EPANET, XML de WNT, redes de tuberías LandXML 1.2, superficies TIN LandXML y datos para dimensionamiento de tuberías.

Requiere QGIS 3.38 o posterior.

## Recetas

Cada viñeta siguiente es un algoritmo de WNT en Processing. El texto posterior al nombre del algoritmo resume el flujo de trabajo que cubre.

### Construir

Proceso disponible:

- `Red desde líneas` - Genera capas de nodos y elementos lineales con estructura EPANET a partir de líneas CAD/GIS. Soporta líneas multipart, fusión de extremos por tolerancia, elevaciones de nodo desde valores cero, valores Z de línea, rásteres MDE o una superficie TIN LandXML seleccionada, y campos opcionales de grado/topología.

### Demanda

Procesos disponibles:

- `Asignar demanda` - Asigna uno o varios campos de demanda desde entidades de origen a los nodos de red más cercanos y crea líneas de asignación.
- `Conectar por distancia` - Conecta entidades de origen y destino por distancia mínima, con límites opcionales de número de conexiones y distancia máxima.
- `Actualizar asignación` - Recalcula asignaciones de demanda después de editar manualmente las líneas de asignación.

### Exportar

Procesos disponibles:

- `Exportar modelo EPANET a archivo INP` - Escribe un modelo EPANET desde seis capas tipadas de nudos de consumo (JUNCTIONS), embalses (RESERVOIRS), depósitos (TANKS), tuberías (PIPES), bombas (PUMPS) y válvulas (VALVES). Puede actualizar un `.inp` existente conservando sus demás secciones o crear un modelo EPANET 2.0/2.2 nuevo con opciones hidráulicas editables.
- `Demanda a archivo de escenario de EPANET (.scn)` - Escribe un escenario EPANET de demandas desde un campo de demanda de nodos seleccionado.
- `Propiedades de tuberías a archivo de escenario de EPANET (.scn)` - Escribe un escenario EPANET de tuberías con valores de diámetro y rugosidad para elementos lineales de tipo tubería.
- `Red a XML` - Escribe WNT Network XML con datos de red versionados y conserva dominios de propiedades EPANET, SWMM, LandXML y personalizados, o escribe una red de tuberías LandXML 1.2.
- `Red a archivo de datos Pipe Sizer (.pro)` - Escribe datos de entrada para Pipe Sizer con secciones `[SETTINGS]`, `[PRESSURES]`, `[FIRE_SCENARIOS]` y `[PIPES]`, incluyendo factores punta/incendio, presiones requeridas y escenarios opcionales de incendio a partir de pares de hidrantes.
- `Red a archivo de datos para optimización de tuberías a presión (.ext)` - Escribe datos de entrada para PPNO (`Pressurized Pipe Network Optimizer`) desde capas de red, un modelo EPANET `.inp` y un catálogo de tuberías `.cat`. Consulta https://github.com/hidronexo/ppno.

### Incendio

Proceso disponible:

- `Pares de hidrantes` - Genera pares de hidrantes/escenarios de cálculo desde una capa de hidrantes, excluyendo pares separados por una distancia mayor que la separación máxima. La salida puede usarse como escenarios de incendio en el exportador Pipe Sizer `.pro`.

### Grafo

Procesos disponibles:

- `Clasificar` - Clasifica elementos lineales como ramificados o mallados y asigna un `zone` globalmente único.
- `Grados de nodo` - Calcula el grado de grafo de cada nodo de la red.
- `Red a archivo de grafo` - Exporta la topología de la red a Trivial Graph Format (TGF).
- `Validar` - Informa nodos huérfanos, nodos duplicados, elementos lineales duplicados, elementos lineales con extremos no definidos y bucles.

### Importar

Procesos disponibles:

- `Configurar biblioteca EPANET` - Define la ruta de la biblioteca del toolkit de EPANET usada para importar resultados EPANET.
  Configura únicamente una biblioteca de confianza del toolkit EPANET 2 instalada en el sistema.
- `Modelo EPANET desde archivo INP` - Importa archivos EPANET `.inp` como seis capas tipadas agrupadas bajo el nombre del modelo. Cada capa registra el INP de origen y la versión de EPANET; no se utiliza un campo JSON genérico.
- `Importar red desde LandXML` - Importa una o varias redes de tuberías a presión, saneamiento o pluviales en formato LandXML 1.2 como capas WNT de nodos y elementos lineales, conservando el sistema de referencia de coordenadas declarado cuando está disponible.
- `Resultados de EPANET` - Importa resultados hidráulicos, resultados de calidad o ambos desde simulaciones EPANET.
- `Red desde XML` - Importa archivos WNT Network XML, incluidas versiones de red seleccionadas, o importa redes de tuberías LandXML 1.2 como capas WNT de nodos y elementos lineales.

### Modificar

Procesos disponibles:

- `Elevación de nodos desde MDE` - Añade o actualiza elevaciones de nodos desde un ráster MDE.
- `Elevación de nodos desde TIN (LandXML)` - Añade o actualiza elevaciones de nodos desde una superficie TIN LandXML seleccionada.
- `Dividir líneas en puntos` - Divide entidades de línea en posiciones de puntos.
- `Fusionar redes` - Fusiona dos redes y valida el grafo final antes de crear las capas de salida.

## Empaquetado

Ejecutar desde un entorno de desarrollo activo:

```bash
python package_wnt.py
```

HIDRONEXO (opensource@hidronexo.com)

## Version 1.6.0 model workflows

EPANET inputs and outputs use JUNCTIONS, RESERVOIRS, TANKS, PIPES, PUMPS and
VALVES. A pipe check valve is `PIPES.status = CV`; its start/end order is its
allowed flow direction. CVPIPE is internal/legacy vocabulary, not a seventh layer.

- INP export keeps the six selectors outside advanced options. Emitters, energy,
  quality/reactions, calculation stability, times and reports use family-labelled
  advanced options. Disabled controls retain their values. Existing-model mode
  preserves global settings, untouched objects and omitted optional properties.
- Scratch models can load PATTERNS and CURVES from an INP definitions file.
  References are validated; a pattern reference never invents a pattern.
  JUNCTIONS.demand_categories holds one `demand [pattern] ; category` line per
  additional demand definition. When populated, these are the authoritative
  [DEMANDS] entries, as in EPANET; the junction base demand is not added again.
- Graph processes evaluate all selected categories together. Results retain ID
  and time in separate category tables. Merge remaps both global ID namespaces
  and endpoints; coincident reservoirs/tanks are not automatically coalesced.
  Only junctions with matching attributes may merge by proximity.
- Multi-layer update operations remain in QGIS edit buffers for review/save.
  No sequential commit across unrelated providers is presented as atomic.
- WNT XML supports typed EPANET layers and a separate generic nodes/links mode.
  Generic SWMM/LandXML geometry workflows are retained; a LandXML water network
  does not imply complete EPANET hydraulic properties.
- Pipe Sizer writes .pro/.psr (three catalog columns); PPNO writes .ext/.cat
  (four columns including price). Both validate actual INP category membership
  and preserve zero pressure. Extended-period Pipe Sizer exports omit fire
  scenarios and use the peak-pressure constraint; steady-state exports support
  fire_flow_1/fire_flow_2 aliases and optional fire-pressure fallback.
- Saved two-layer INP callers have an explicit type/property adapter. Canonical
  and contradictory legacy inputs are rejected. New category outputs use
  OUTPUT_JUNCTIONS, OUTPUT_PIPES, etc.; saved models must reconnect output names.

Field-level REPORT filters/precision and new rule/control editing are not form
parameters. Existing INP sections are retained; this exporter is not a reversible
text editor and does not promise byte-identical comments or whitespace.
EPANET 2.2 directives follow the [official EPA manual](https://usepa.github.io/EPANET2.2/back_matter.html).

Release checks: use Pixi test/lint/typecheck; run QGIS-marked tests with QGIS
Python. Set WNT_EPANET_LIBRARY to an external toolkit to enable the four native
engine acceptance cases. Build with `python package_wnt.py --skip-deploy` and
run `verify_qgis_package.py wnt/wnt.zip` using QGIS Python (Processing plugins
must be on its module path). No EPANET library or private project is bundled.
