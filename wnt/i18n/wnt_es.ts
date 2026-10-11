<?xml version='1.0' encoding='utf-8'?>
<TS version="2.1" language="es">
    <context>
        <name>WaterNetworkTools</name>
        <message>
            <source>&lt;p&gt;Analyses the network graph and reports topology problems.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Orphan nodes.&lt;/li&gt;
&lt;li&gt;Duplicate nodes.&lt;/li&gt;
&lt;li&gt;Links with undefined endpoints.&lt;/li&gt;
&lt;li&gt;Duplicate links.&lt;/li&gt;
&lt;li&gt;Loops, where start and end node are the same.&lt;/li&gt;
&lt;li&gt;Can create new output layers or update the input node and link layers.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Detected problems are written to the &lt;code&gt;problems&lt;/code&gt; field.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Analiza el grafo de la red e informa de problemas topológicos.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Nodos huérfanos.&lt;/li&gt;
&lt;li&gt;Nodos duplicados.&lt;/li&gt;
&lt;li&gt;Links con extremos no definidos.&lt;/li&gt;
&lt;li&gt;Links duplicados.&lt;/li&gt;
&lt;li&gt;Bucles, donde el nodo inicial y final es el mismo.&lt;/li&gt;
&lt;li&gt;Puede crear nuevas capas de salida o actualizar las capas de nodos y links de entrada.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Los problemas detectados se escriben en el campo &lt;code&gt;problems&lt;/code&gt;.&lt;/p&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_assign_demand.py" line="67" />
            <source>&lt;p&gt;Assigns demand from a &lt;b&gt;source layer&lt;/b&gt; to a &lt;b&gt;target node layer&lt;/b&gt; using the nearest target feature.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Both input layers must contain an &lt;code&gt;id&lt;/code&gt; field.&lt;/li&gt;
&lt;li&gt;The selected source demand fields are copied and accumulated in the target layer.&lt;/li&gt;
&lt;li&gt;The output assignment layer stores the connection lines between source and target features.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Use &lt;b&gt;Update assignment&lt;/b&gt; after editing assignment lines.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Asigna demandas desde una &lt;b&gt;capa de origen&lt;/b&gt; a una &lt;b&gt;capa de nodos de destino&lt;/b&gt; usando la entidad de destino más cercana.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Ambas capas de entrada deben contener un campo &lt;code&gt;id&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Los campos de demanda seleccionados de la capa de origen se copian y acumulan en la capa de destino.&lt;/li&gt;
&lt;li&gt;La capa de asignaciones de salida almacena las líneas de conexión entre las entidades de origen y destino.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Usa &lt;b&gt;Update assignment&lt;/b&gt; después de editar las líneas de asignación.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Builds EPANET-style network node and link layers from input line features.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Output geometries are created in the selected coordinate reference system.&lt;/li&gt;
&lt;li&gt;Line endpoints closer than the tolerance are merged into a single node.&lt;/li&gt;
&lt;li&gt;The node layer contains &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt;, and &lt;code&gt;elevation&lt;/code&gt;; node type defaults to &lt;code&gt;JUNCTION&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;The link layer contains &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;start&lt;/code&gt;, &lt;code&gt;end&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt;, and &lt;code&gt;length&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;When a &lt;code&gt;link_type&lt;/code&gt; field is selected, link type values are copied from the input features.&lt;/li&gt;
&lt;li&gt;Optional fields can add node degree and link topology data.&lt;/li&gt;
&lt;li&gt;Node elevations can be left at zero, copied from line endpoint Z values, sampled from a DEM raster, or interpolated from a LandXML TIN surface.&lt;/li&gt;
&lt;li&gt;Input layer fields are preserved in the output link layer.&lt;/li&gt;
&lt;li&gt;Multipart geometries are split into individual output links.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Looped lines are rejected.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Construye las dos capas: nodos y links de una red con estructura EPANET a partir de las líneas de entrada.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Las geometrías de salida se crean en el sistema de referencia de coordenadas seleccionado.&lt;/li&gt;
&lt;li&gt;Los extremos de líneas separados por una distancia menor que la tolerancia se fusionan en un único nodo.&lt;/li&gt;
&lt;li&gt;La capa de nodos contiene &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt; y &lt;code&gt;elevation&lt;/code&gt;; el tipo de nodo por defecto es &lt;code&gt;JUNCTION&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;La capa de links contiene &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;start&lt;/code&gt;, &lt;code&gt;end&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt; y &lt;code&gt;length&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Cuando se selecciona un campo de tipo de link, se asigna a los links un tipo: &lt;code&gt;PIPE&lt;/code&gt;, &lt;code&gt;CV&lt;/code&gt;, &lt;code&gt;PUMP&lt;/code&gt;, &lt;code&gt;PRV&lt;/code&gt;, &lt;code&gt;PSV&lt;/code&gt;, &lt;code&gt;PBV&lt;/code&gt;, &lt;code&gt;FCV&lt;/code&gt;, &lt;code&gt;TCV&lt;/code&gt;, &lt;code&gt;GVP&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Con los campos opcionales se pueden añadir el grado de nodo y la topología de los links.&lt;/li&gt;
&lt;li&gt;Las elevaciones de nodos pueden dejarse a cero, copiarse desde los valores de elevación de los extremos de la capa de entrada, muestrearse desde un ráster DEM o interpolarse desde una superficie TIN LandXML.&lt;/li&gt;
&lt;li&gt;Los campos de la capa de entrada se conservan en la capa de links de salida.&lt;/li&gt;
&lt;li&gt;Las geometrías multiparte se separan en links de salida individuales.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Las líneas en bucle se rechazan.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Calculates the graph degree of each network node.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;The degree is the number of links connected to a node.&lt;/li&gt;
&lt;li&gt;Orphan nodes have degree &lt;code&gt;0&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Leaf nodes have degree &lt;code&gt;1&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Continuity nodes have degree &lt;code&gt;2&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Can create a new output layer or update the input node layer.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Results are written to the &lt;code&gt;degree&lt;/code&gt; field.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Calcula el grado de cada nodo de la red.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;El grado es el número de links conectados a un nodo.&lt;/li&gt;
&lt;li&gt;Los nodos huérfanos tienen grado &lt;code&gt;0&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Los nodos hoja tienen grado &lt;code&gt;1&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Los nodos de continuidad tienen grado &lt;code&gt;2&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Puede crear una capa de salida nueva o actualizar la capa de nodos de entrada.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Los resultados se escriben en el campo &lt;code&gt;degree&lt;/code&gt;.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Classifies network links into branched and meshed areas.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Adds or updates &lt;code&gt;topology&lt;/code&gt;: &lt;code&gt;branched&lt;/code&gt; or &lt;code&gt;mesh&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Adds or updates &lt;code&gt;zone&lt;/code&gt;: subnetwork identifier.&lt;/li&gt;
&lt;li&gt;Can create a new output layer or update the input link layer.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Use this algorithm to support network sectorization.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Clasifica los links de la red en áreas ramificadas y malladas.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Añade o actualiza &lt;code&gt;topology&lt;/code&gt;: &lt;code&gt;branched&lt;/code&gt; o &lt;code&gt;mesh&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Añade o actualiza &lt;code&gt;zone&lt;/code&gt;: identificador de subred.&lt;/li&gt;
&lt;li&gt;Puede crear una capa de salida nueva o actualizar la capa de links de entrada.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Usa este algoritmo como apoyo a la sectorización de redes.&lt;/p&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_classify.py" line="63" />
            <source>&lt;p&gt;Classifies network links into branched and meshed areas.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Adds or updates &lt;code&gt;topology&lt;/code&gt;: &lt;code&gt;branched&lt;/code&gt; or &lt;code&gt;mesh&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Adds or updates &lt;code&gt;zones&lt;/code&gt;: subnetwork identifier.&lt;/li&gt;
&lt;li&gt;Can create a new output layer or update the input link layer.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Use this algorithm to support network sectorization.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Clasifica los links de la red en áreas ramificadas y malladas.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Añade o actualiza &lt;code&gt;topology&lt;/code&gt;: &lt;code&gt;branched&lt;/code&gt; o &lt;code&gt;mesh&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Añade o actualiza &lt;code&gt;zones&lt;/code&gt;: identificador de subred.&lt;/li&gt;
&lt;li&gt;Puede crear una capa de salida nueva o actualizar la capa de links de entrada.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Usa este algoritmo como apoyo a la sectorización de redes.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Connects features from a &lt;b&gt;source layer&lt;/b&gt; to a &lt;b&gt;target layer&lt;/b&gt; by minimum distance.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Both layers must contain an &lt;code&gt;id&lt;/code&gt; field.&lt;/li&gt;
&lt;li&gt;The maximum number of connections and maximum distance limit the generated links.&lt;/li&gt;
&lt;li&gt;The output is a line layer representing the connections.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Conecta entidades de una &lt;b&gt;capa de origen&lt;/b&gt; con una &lt;b&gt;capa de destino&lt;/b&gt; por distancia mínima.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Ambas capas deben contener un campo &lt;code&gt;id&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;El número máximo de conexiones y la distancia máxima limitan los links generados.&lt;/li&gt;
&lt;li&gt;La salida es una capa de links que representa las conexiones.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Creates a PPNO &lt;code&gt;.ext&lt;/code&gt; data file for pipe sizing.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;The required pressure must be stored in a node layer field.&lt;/li&gt;
&lt;li&gt;The pipe group must be stored in a link layer field.&lt;/li&gt;
&lt;li&gt;The EPANET &lt;code&gt;.inp&lt;/code&gt; file must contain the model to optimize.&lt;/li&gt;
&lt;li&gt;The pipe catalog is selected directly as an external &lt;code&gt;.cat&lt;/code&gt; file.&lt;/li&gt;
&lt;li&gt;PPNO runs EPANET simulations, applies minimum pressure constraints, and optionally runs global optimization algorithms.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Crea un archivo de datos PPNO &lt;code&gt;.ext&lt;/code&gt; para dimensionar tuberías.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;La presión requerida debe estar almacenada en un campo de la capa de nodos.&lt;/li&gt;
&lt;li&gt;El grupo de tuberías debe estar almacenado en un campo de la capa de links.&lt;/li&gt;
&lt;li&gt;El archivo EPANET &lt;code&gt;.inp&lt;/code&gt; debe contener el modelo que se va a optimizar.&lt;/li&gt;
&lt;li&gt;El catálogo de tuberías se selecciona directamente como archivo externo &lt;code&gt;.cat&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;PPNO ejecuta simulaciones EPANET, aplica restricciones de presión mínima y opcionalmente ejecuta algoritmos de optimización global.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Creates a pipesizing &lt;code&gt;.pro&lt;/code&gt; data file.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;The required peak-flow and fire-flow pressures must be stored in node layer fields.&lt;/li&gt;
&lt;li&gt;The pipe series name must be stored in a link layer field.&lt;/li&gt;
&lt;li&gt;Optional hydrant pair/fire scenario lines can be written from a hydrant pairs layer.&lt;/li&gt;
&lt;li&gt;The EPANET &lt;code&gt;.inp&lt;/code&gt; file path is written relative to the &lt;code&gt;.pro&lt;/code&gt; file.&lt;/li&gt;
&lt;li&gt;The pipe catalog is selected directly as an external &lt;code&gt;.cat&lt;/code&gt; file.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Crea un archivo de datos pipesizing &lt;code&gt;.pro&lt;/code&gt;.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Las presiones requeridas para caudal punta e incendio deben estar almacenadas en campos de la capa de nodos.&lt;/li&gt;
&lt;li&gt;El nombre de la serie de tuberías debe estar almacenado en un campo de la capa de links.&lt;/li&gt;
&lt;li&gt;Opcionalmente se pueden escribir pares de hidrantes/escenarios de incendio desde una capa de pares de hidrantes.&lt;/li&gt;
&lt;li&gt;La ruta del archivo EPANET &lt;code&gt;.inp&lt;/code&gt; se escribe relativa al archivo &lt;code&gt;.pro&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;El catálogo de tuberías se selecciona directamente como archivo externo &lt;code&gt;.cat&lt;/code&gt;.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_network_to_pipesizing.py" line="82" />
            <source>&lt;p&gt;Creates a pipesizing &lt;code&gt;.pro&lt;/code&gt; data file.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;The required pressure must be stored in a node layer field.&lt;/li&gt;
&lt;li&gt;The pipe series name must be stored in a link layer field.&lt;/li&gt;
&lt;li&gt;The EPANET &lt;code&gt;.inp&lt;/code&gt; file path is written relative to the &lt;code&gt;.pro&lt;/code&gt; file.&lt;/li&gt;
&lt;li&gt;The pipe catalog is selected directly as an external &lt;code&gt;.cat&lt;/code&gt; file.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Crea un archivo de datos pipesizing &lt;code&gt;.pro&lt;/code&gt;.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;La presión requerida debe estar almacenada en un campo de la capa de nodos.&lt;/li&gt;
&lt;li&gt;El nombre de la serie de tuberías debe estar almacenado en un campo de la capa de links.&lt;/li&gt;
&lt;li&gt;La ruta del archivo EPANET &lt;code&gt;.inp&lt;/code&gt; se escribe relativa al archivo &lt;code&gt;.pro&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;El catálogo de tuberías se selecciona directamente como archivo externo &lt;code&gt;.cat&lt;/code&gt;.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Creates an EPANET &lt;code&gt;.inp&lt;/code&gt; file from network node and link layers.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Output mode “Add links and nodes to existing EPANET model” adds the selected node and link layers to an existing EPANET &lt;code&gt;.inp&lt;/code&gt; model; EPANET version and flow units are ignored.&lt;/li&gt;
&lt;li&gt;Output mode “Create EPANET model from scratch” creates a new EPANET model from a minimal internal template; select the EPANET version and flow units.&lt;/li&gt;
&lt;li&gt;Adds nodes to &lt;code&gt;JUNCTIONS&lt;/code&gt;, &lt;code&gt;RESERVOIRS&lt;/code&gt;, or &lt;code&gt;TANKS&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Adds links to &lt;code&gt;PIPES&lt;/code&gt;, &lt;code&gt;PUMPS&lt;/code&gt;, or &lt;code&gt;VALVES&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;The final network graph is validated before writing the EPANET file.&lt;/li&gt;
&lt;li&gt;Exports coordinates and intermediate vertices.&lt;/li&gt;
&lt;li&gt;Pipe diameter and roughness are not exported; add them using scenario files.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Crea un archivo EPANET &lt;code&gt;.inp&lt;/code&gt; desde capas de nodos y links de red.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;El modo de salida “Add links and nodes to existing EPANET model” añade las capas de nodos y links seleccionadas a un modelo EPANET &lt;code&gt;.inp&lt;/code&gt; existente; se ignoran la versión de EPANET y las unidades de caudal.&lt;/li&gt;
&lt;li&gt;El modo de salida “Create EPANET model from scratch” crea un modelo EPANET nuevo desde una plantilla interna mínima; selecciona la versión de EPANET y las unidades de caudal.&lt;/li&gt;
&lt;li&gt;Añade nodos a &lt;code&gt;JUNCTIONS&lt;/code&gt;, &lt;code&gt;RESERVOIRS&lt;/code&gt; o &lt;code&gt;TANKS&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Añade links a &lt;code&gt;PIPES&lt;/code&gt;, &lt;code&gt;PUMPS&lt;/code&gt; o &lt;code&gt;VALVES&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;El grafo final de la red se valida antes de escribir el archivo EPANET.&lt;/li&gt;
&lt;li&gt;Exporta coordenadas y vértices intermedios.&lt;/li&gt;
&lt;li&gt;El diámetro y la rugosidad de tuberías no se exportan; añádelos usando archivos de escenario.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_network_to_epanet.py" line="76" />
            <source>&lt;p&gt;Creates an EPANET &lt;code&gt;.inp&lt;/code&gt; file from network node and link layers.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Workflow A adds the selected node and link layers to an existing EPANET &lt;code&gt;.inp&lt;/code&gt; model; EPANET version and flow units are ignored.&lt;/li&gt;
&lt;li&gt;Workflow B creates a new EPANET model from a minimal internal template; select the EPANET version and flow units.&lt;/li&gt;
&lt;li&gt;Adds nodes to &lt;code&gt;JUNCTIONS&lt;/code&gt;, &lt;code&gt;RESERVOIRS&lt;/code&gt;, or &lt;code&gt;TANKS&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Adds links to &lt;code&gt;PIPES&lt;/code&gt;, &lt;code&gt;PUMPS&lt;/code&gt;, or &lt;code&gt;VALVES&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Exports coordinates and intermediate vertices.&lt;/li&gt;
&lt;li&gt;Pipe diameter and roughness are not exported; add them using scenario files.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Crea un archivo EPANET &lt;code&gt;.inp&lt;/code&gt; desde capas de nodos y links de red.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;El flujo A añade las capas de nodos y links seleccionadas a un modelo EPANET &lt;code&gt;.inp&lt;/code&gt; existente; se ignoran la versión de EPANET y las unidades de caudal.&lt;/li&gt;
&lt;li&gt;El flujo B crea un modelo EPANET nuevo desde una plantilla interna mínima; selecciona la versión de EPANET y las unidades de caudal.&lt;/li&gt;
&lt;li&gt;Añade nodos a &lt;code&gt;JUNCTIONS&lt;/code&gt;, &lt;code&gt;RESERVOIRS&lt;/code&gt; o &lt;code&gt;TANKS&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Añade links a &lt;code&gt;PIPES&lt;/code&gt;, &lt;code&gt;PUMPS&lt;/code&gt; o &lt;code&gt;VALVES&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Exporta coordenadas y vértices intermedios.&lt;/li&gt;
&lt;li&gt;El diámetro y la rugosidad de tuberías no se exportan; añádelos usando archivos de escenario.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Creates an EPANET &lt;code&gt;.scn&lt;/code&gt; scenario file with pipe diameters and roughness values.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Diameters are read from the selected mandatory diameter field.&lt;/li&gt;
&lt;li&gt;Roughness values are read from the selected mandatory roughness field.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Import the generated file in EPANET using &lt;b&gt;File &amp;gt; Import &amp;gt; Scenario&lt;/b&gt;.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Crea un archivo de escenario EPANET &lt;code&gt;.scn&lt;/code&gt; con diámetros y rugosidades de tuberías.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Los diámetros se leen desde el campo obligatorio de diámetro seleccionado.&lt;/li&gt;
&lt;li&gt;Las rugosidades se leen desde el campo obligatorio de rugosidad seleccionado.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Importa el archivo generado en EPANET usando &lt;b&gt;File &amp;gt; Import &amp;gt; Scenario&lt;/b&gt;.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Creates an EPANET demand scenario file.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Each demand category must be stored in a field of the node layer.&lt;/li&gt;
&lt;li&gt;EPANET patterns must use the same names as the selected demand fields.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Import the generated file in EPANET using &lt;b&gt;File &amp;gt; Import &amp;gt; Scenario&lt;/b&gt;.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Crea un archivo de escenario de demandas EPANET &lt;code&gt;.scn&lt;/code&gt;.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Cada categoría de demanda debe estar almacenada en un campo de la capa de nodos.&lt;/li&gt;
&lt;li&gt;Los patrones EPANET deben usar los mismos nombres que los campos de demanda seleccionados.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Importa el archivo generado en EPANET usando &lt;b&gt;File &amp;gt; Import &amp;gt; Scenario&lt;/b&gt;.&lt;/p&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_hydrant_pairs.py" line="66" />
            <source>&lt;p&gt;Creates hydrant pairs from a hydrant node layer.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;The output is a line layer connecting paired hydrants.&lt;/li&gt;
&lt;li&gt;The line geometry helps verify that pairs can be connected through public space.&lt;/li&gt;
&lt;li&gt;Pairs farther apart than the maximum separation are not generated.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Crea pares de hidrantes a partir de una capa de nodos de hidrantes.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;La salida es una capa de líneas que conecta los hidrantes emparejados.&lt;/li&gt;
&lt;li&gt;La geometría de las líneas ayuda a comprobar si los pares pueden conectarse por espacio público.&lt;/li&gt;
&lt;li&gt;No se generan pares separados por una distancia mayor que la separación máxima.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Creates hydrant pairs/calculation scenarios from a hydrant layer.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;The output is a line layer connecting paired hydrants/fire scenarios.&lt;/li&gt;
&lt;li&gt;The line geometry helps verify that pairs can be connected through public space.&lt;/li&gt;
&lt;li&gt;Pairs farther apart than the maximum separation are not generated.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Crea pares de hidrantes/escenarios de cálculo a partir de una capa de hidrantes.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;La salida es una capa de líneas que conecta los hidrantes/escenarios de incendio emparejados.&lt;/li&gt;
&lt;li&gt;La geometría de las líneas ayuda a verificar que los pares pueden conectarse por espacio público.&lt;/li&gt;
&lt;li&gt;No se generan pares separados por una distancia mayor que la separación máxima.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Exports network node and link layers to XML.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;&lt;code&gt;WNT Network XML&lt;/code&gt; stores topology and domain property bags using the network name as both network and version name.&lt;/li&gt;
&lt;li&gt;&lt;code&gt;LandXML 1.2&lt;/code&gt; writes a pipe network with the selected standard network type: sanitary, storm, water or other.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Exporta capas de nodos y links de red a XML.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;&lt;code&gt;WNT Network XML&lt;/code&gt; almacena la topología y las propiedades de dominio usando el nombre de red como nombre de red y de versión.&lt;/li&gt;
&lt;li&gt;&lt;code&gt;LandXML 1.2&lt;/code&gt; escribe una red de tuberías con el tipo de red estándar seleccionado: sanitary, storm, water u other.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Exports the network topology to a Trivial Graph Format file.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Input node and link layers must contain valid network identifiers.&lt;/li&gt;
&lt;li&gt;The output &lt;code&gt;.tgf&lt;/code&gt; file can be opened in graph tools such as yEd.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Exporta la topología de la red a un archivo en formato Trivial Graph Format.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Las capas de nodos y links de entrada deben contener identificadores de red válidos.&lt;/li&gt;
&lt;li&gt;El archivo &lt;code&gt;.tgf&lt;/code&gt; de salida puede abrirse en herramientas de grafos como yEd.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Imports an EPANET &lt;code&gt;.inp&lt;/code&gt; file and creates node and link layers.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Node attributes are &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt;, &lt;code&gt;elevation&lt;/code&gt; and &lt;code&gt;epanet&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Link attributes are &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;start&lt;/code&gt;, &lt;code&gt;end&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt; and &lt;code&gt;epanet&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;The &lt;code&gt;epanet&lt;/code&gt; field stores type-specific EPANET properties as JSON.&lt;/li&gt;
&lt;li&gt;Quality, source, mixing, reaction, status, energy, demand and tag data are preserved when present.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Importa un archivo &lt;code&gt;.inp&lt;/code&gt; de EPANET y crea capas de nodos y links.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Los atributos de nodos son &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt;, &lt;code&gt;elevation&lt;/code&gt; y &lt;code&gt;epanet&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Los atributos de links son &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;start&lt;/code&gt;, &lt;code&gt;end&lt;/code&gt;, &lt;code&gt;type&lt;/code&gt; y &lt;code&gt;epanet&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;El campo &lt;code&gt;epanet&lt;/code&gt; almacena en JSON las propiedades EPANET específicas de cada tipo.&lt;/li&gt;
&lt;li&gt;Los datos de calidad, fuente, mezcla, reacción, estado, energía, demanda y etiquetas se conservan cuando existen.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Imports hydraulic and quality results from an EPANET simulation.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Node results: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;demand&lt;/code&gt;, &lt;code&gt;head&lt;/code&gt;, &lt;code&gt;pressure&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Link results: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;flow&lt;/code&gt;, &lt;code&gt;velocity&lt;/code&gt;, &lt;code&gt;headloss&lt;/code&gt;, &lt;code&gt;status&lt;/code&gt;, &lt;code&gt;setting&lt;/code&gt;, &lt;code&gt;energy&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Quality results: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;quality&lt;/code&gt;.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Configure the EPANET toolkit library before running this algorithm.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Importa resultados hidráulicos y de calidad desde una simulación EPANET.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Resultados de nodos: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;demand&lt;/code&gt;, &lt;code&gt;head&lt;/code&gt;, &lt;code&gt;pressure&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Resultados de links: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;flow&lt;/code&gt;, &lt;code&gt;velocity&lt;/code&gt;, &lt;code&gt;headloss&lt;/code&gt;, &lt;code&gt;status&lt;/code&gt;, &lt;code&gt;setting&lt;/code&gt;, &lt;code&gt;energy&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Resultados de calidad: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;id&lt;/code&gt;, &lt;code&gt;quality&lt;/code&gt;.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Configura la biblioteca del toolkit de EPANET antes de ejecutar este algoritmo.&lt;/p&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_results_from_epanet.py" line="62" />
            <source>&lt;p&gt;Imports hydraulic results from an EPANET simulation.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Node results: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;demand&lt;/code&gt;, &lt;code&gt;head&lt;/code&gt;, &lt;code&gt;pressure&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Link results: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;flow&lt;/code&gt;, &lt;code&gt;velocity&lt;/code&gt;, &lt;code&gt;headloss&lt;/code&gt;, &lt;code&gt;status&lt;/code&gt;, &lt;code&gt;setting&lt;/code&gt;, &lt;code&gt;energy&lt;/code&gt;.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Configure the EPANET toolkit library before running this algorithm.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Importa resultados hidráulicos de una simulación de EPANET.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Resultados de nodos: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;demand&lt;/code&gt;, &lt;code&gt;head&lt;/code&gt;, &lt;code&gt;pressure&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Resultados de links: &lt;code&gt;time&lt;/code&gt;, &lt;code&gt;flow&lt;/code&gt;, &lt;code&gt;velocity&lt;/code&gt;, &lt;code&gt;headloss&lt;/code&gt;, &lt;code&gt;status&lt;/code&gt;, &lt;code&gt;setting&lt;/code&gt;, &lt;code&gt;energy&lt;/code&gt;.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Configura la biblioteca del toolkit de EPANET antes de ejecutar este algoritmo.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Imports network node and link layers from XML.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;&lt;code&gt;WNT Network XML&lt;/code&gt; files are loaded by network name and version; empty version loads the latest version for each selected network.&lt;/li&gt;
&lt;li&gt;&lt;code&gt;LandXML 1.2&lt;/code&gt; pipe networks are converted to WNT node and link layers.&lt;/li&gt;
&lt;li&gt;Network names are written as a comma or semicolon separated list. If empty, all networks are loaded.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Importa capas de nodos y links de red desde XML.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Los archivos &lt;code&gt;WNT Network XML&lt;/code&gt; se cargan por nombre de red y versión; si la versión está vacía, se carga la última versión de cada red seleccionada.&lt;/li&gt;
&lt;li&gt;Las redes de tuberías &lt;code&gt;LandXML 1.2&lt;/code&gt; se convierten a capas WNT de nodos y links.&lt;/li&gt;
&lt;li&gt;Los nombres de red se escriben como una lista separada por comas o punto y coma. Si se deja vacío, se cargan todas las redes.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Merges two networks from their node and link layers.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Nodes from the second network are connected to nodes from the first network when they are within the tolerance distance in the selected output CRS units.&lt;/li&gt;
&lt;li&gt;Connected nodes keep the &lt;code&gt;id&lt;/code&gt; and position of the first network node.&lt;/li&gt;
&lt;li&gt;Incident links from the second network are renamed and their endpoints are snapped to connected first-network nodes.&lt;/li&gt;
&lt;li&gt;Links from the second network must not already exist in the first network by &lt;code&gt;id&lt;/code&gt; or by matching endpoints within the tolerance distance.&lt;/li&gt;
&lt;li&gt;Near misses are reported when second-network nodes are closer than the configured near-merge factor times the tolerance.&lt;/li&gt;
&lt;li&gt;Output node and link layers are written in the selected CRS.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Fusiona dos redes a partir de sus capas de nodos y links.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Los nodos de la segunda red se conectan con nodos de la primera red cuando están dentro de la tolerancia en las unidades del SRC de salida seleccionado.&lt;/li&gt;
&lt;li&gt;Los nodos conectados conservan el &lt;code&gt;id&lt;/code&gt; y la posición del nodo de la primera red.&lt;/li&gt;
&lt;li&gt;Los links incidentes de la segunda red se renombran y sus extremos se ajustan a los nodos conectados de la primera red.&lt;/li&gt;
&lt;li&gt;Los links de la segunda red no deben existir ya en la primera red por &lt;code&gt;id&lt;/code&gt; ni por extremos coincidentes dentro de la tolerancia.&lt;/li&gt;
&lt;li&gt;Se informa de aproximaciones cuando los nodos de la segunda red están más cerca que el factor configurado por la tolerancia.&lt;/li&gt;
&lt;li&gt;Las capas de nodos y links de salida se escriben en el SRC seleccionado.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_merge_networks.py" line="243" />
            <source>&lt;p&gt;Merges two networks from their node and link layers.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Nodes from the second network are connected to nodes from the first network when they are within the tolerance distance in the selected output CRS units.&lt;/li&gt;
&lt;li&gt;Connected nodes keep the &lt;code&gt;id&lt;/code&gt; and position of the first network node.&lt;/li&gt;
&lt;li&gt;Incident links from the second network are renamed and their endpoints are snapped to connected first-network nodes.&lt;/li&gt;
&lt;li&gt;Links from the second network must not already exist in the first network by &lt;code&gt;id&lt;/code&gt; or by matching endpoints within the tolerance distance.&lt;/li&gt;
&lt;li&gt;Near misses are reported when second-network nodes are closer than the configured near-merge factor times the tolerance.&lt;/li&gt;
&lt;li&gt;Output node and link layers are written in the selected CRS.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Validate the merged network after running this algorithm.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Fusiona dos redes a partir de sus capas de nodos y links.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Los nodos de la segunda red se conectan con nodos de la primera red cuando están dentro de la tolerancia en las unidades del SRC de salida seleccionado.&lt;/li&gt;
&lt;li&gt;Los nodos conectados conservan el &lt;code&gt;id&lt;/code&gt; y la posición del nodo de la primera red.&lt;/li&gt;
&lt;li&gt;Los links incidentes de la segunda red se renombran y sus extremos se ajustan a los nodos conectados de la primera red.&lt;/li&gt;
&lt;li&gt;Los links de la segunda red no deben existir ya en la primera red por &lt;code&gt;id&lt;/code&gt; ni por extremos coincidentes dentro de la tolerancia.&lt;/li&gt;
&lt;li&gt;Se informa de aproximaciones cuando los nodos de la segunda red están más cerca que el factor configurado por la tolerancia.&lt;/li&gt;
&lt;li&gt;Las capas de nodos y links de salida se escriben en el SRC seleccionado.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Valida la red fusionada después de ejecutar este algoritmo.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Sets node elevations from a raster DEM.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Reads elevation values from the DEM at each node position.&lt;/li&gt;
&lt;li&gt;Writes the values to the selected elevation field.&lt;/li&gt;
&lt;li&gt;Nodes outside the raster extent are reported as skipped and kept unchanged.&lt;/li&gt;
&lt;li&gt;Can create a new output layer or update the input node layer.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Establece elevaciones de nodos desde un ráster MDE.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Lee valores de elevación del MDE en la posición de cada nodo.&lt;/li&gt;
&lt;li&gt;Escribe los valores en el campo de elevación seleccionado.&lt;/li&gt;
&lt;li&gt;Los nodos fuera de la extensión del ráster se informan como omitidos y se mantienen sin cambios.&lt;/li&gt;
&lt;li&gt;Puede crear una capa de salida nueva o actualizar la capa de nodos de entrada.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Sets node elevations from one LandXML TIN surface.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;If no surface is selected, the first TIN surface found in the file is used and reported.&lt;/li&gt;
&lt;li&gt;The selected surface is loaded once and searched with its spatial index.&lt;/li&gt;
&lt;li&gt;Can create a new output layer or update the input node layer.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Establece elevaciones de nodos desde una superficie TIN LandXML.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Si no se selecciona ninguna superficie, se usa y se informa la primera superficie TIN encontrada en el archivo.&lt;/li&gt;
&lt;li&gt;La superficie seleccionada se carga una sola vez y se consulta con su índice espacial.&lt;/li&gt;
&lt;li&gt;Puede crear una capa de salida nueva o actualizar la capa de nodos de entrada.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <location filename="../processes/wnt_elevation_from_tin.py" line="67" />
            <source>&lt;p&gt;Sets node elevations from one or more LandXML TIN surfaces.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Surface names are written as a comma or semicolon separated list.&lt;/li&gt;
&lt;li&gt;If no surface is selected, the first TIN surface found in the file is used and reported.&lt;/li&gt;
&lt;li&gt;When several selected surfaces cover the same node, elevations must be consistent.&lt;/li&gt;
&lt;li&gt;Can create a new output layer or update the input node layer.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Establece elevaciones de nodos desde una o varias superficies TIN LandXML.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Los nombres de superficie se escriben como una lista separada por comas o punto y coma.&lt;/li&gt;
&lt;li&gt;Si no se selecciona ninguna superficie, se usa y se informa la primera superficie TIN encontrada en el archivo.&lt;/li&gt;
&lt;li&gt;Cuando varias superficies seleccionadas cubren el mismo nodo, las elevaciones deben ser coherentes.&lt;/li&gt;
&lt;li&gt;Puede crear una capa de salida nueva o actualizar la capa de nodos de entrada.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Sets the path to the EPANET toolkit library.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;The path is stored in &lt;code&gt;toolkit.ini&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Configure this before importing EPANET simulation results.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;EPANET toolkit libraries can be obtained from the EPA EPANET download page or from a compatible EPANET toolkit build.&lt;/p&gt;
        </source>
            <translation>&lt;p&gt;Define la ruta de la biblioteca del toolkit de EPANET.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;La ruta se guarda en &lt;code&gt;toolkit.ini&lt;/code&gt;.&lt;/li&gt;
&lt;li&gt;Configúrala antes de importar resultados de simulaciones de EPANET.&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;Las bibliotecas del toolkit de EPANET pueden obtenerse desde la página de descargas de EPANET de la EPA o desde una compilación compatible del toolkit de EPANET.&lt;/p&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Splits line features at point positions.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Use this algorithm to insert junctions or intermediate nodes into line layers.&lt;/li&gt;
&lt;li&gt;Points are matched to lines using the tolerance in the selected output CRS units.&lt;/li&gt;
&lt;li&gt;Can create a new output layer or replace the input line layer features.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Divide entidades de línea en posiciones de puntos.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Usa este algoritmo para insertar uniones o nodos intermedios en capas de líneas.&lt;/li&gt;
&lt;li&gt;Los puntos se emparejan con las líneas usando la tolerancia en las unidades del SRC de salida seleccionado.&lt;/li&gt;
&lt;li&gt;Puede crear una capa de salida nueva o reemplazar las entidades de la capa de líneas de entrada.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>&lt;p&gt;Updates demand assignments after editing assignment lines.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Recalculates demand values in the target node layer.&lt;/li&gt;
&lt;li&gt;Only the target endpoint of an assignment line can be moved.&lt;/li&gt;
&lt;li&gt;The source endpoint must remain on the original source feature.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Actualiza asignaciones de demanda después de editar líneas de asignación.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Recalcula los valores de demanda en la capa de nodos de destino.&lt;/li&gt;
&lt;li&gt;Solo puede moverse el extremo de destino de una línea de asignación.&lt;/li&gt;
&lt;li&gt;El extremo de origen debe permanecer sobre la entidad de origen original.&lt;/li&gt;
&lt;/ul&gt;</translation>
        </message>
        <message>
            <source>Add node_degree field</source>
            <translation>Añade el grado a los nodos</translation>
        </message>
        <message>
            <source>Add topology and zone fields</source>
            <translation>Añade topología y zona a los links</translation>
        </message>
        <message>
            <source>Add links and nodes to existing EPANET model</source>
            <translation>Añadir links y nodos a un modelo EPANET existente</translation>
        </message>
        <message>
            <source>Build</source>
            <translation>Construir</translation>
        </message>
        <message>
            <source>Classify</source>
            <translation>Clasificar</translation>
        </message>
        <message>
            <source>Create EPANET model from scratch</source>
            <translation>Crear un modelo EPANET desde cero</translation>
        </message>
        <message>
            <source>Create new output layer</source>
            <translation>Crear capa de salida nueva</translation>
        </message>
        <message>
            <source>Demand</source>
            <translation>Demanda</translation>
        </message>
        <message>
            <source>Export</source>
            <translation>Exportar</translation>
        </message>
        <message>
            <source>Fire</source>
            <translation>Incendio</translation>
        </message>
        <message>
            <source>Graph</source>
            <translation>Grafo</translation>
        </message>
        <message>
            <source>Hydrant pairs</source>
            <translation>Pares de hidrantes</translation>
        </message>
        <message>
            <source>Hydraulic and quality results</source>
            <translation>Resultados hidráulicos y de calidad</translation>
        </message>
        <message>
            <source>Hydraulic results</source>
            <translation>Resultados hidráulicos</translation>
        </message>
        <message>
            <source>Import</source>
            <translation>Importar</translation>
        </message>
        <message>
            <source>Merge networks</source>
            <translation>Fusionar redes</translation>
        </message>
        <message>
            <source>Modify</source>
            <translation>Modificar</translation>
        </message>
        <message>
            <source>Network from XML</source>
            <translation>Importar red desde XML</translation>
        </message>
        <message>
            <source>Network to epanet file (.inp)</source>
            <translation>Exportar red a EPANET (.inp)</translation>
        </message>
        <message>
            <source>Network to pipesizing data file (.pro)</source>
            <translation>Exportar red a PipeSizing (.pro)</translation>
        </message>
        <message>
            <source>Network to XML</source>
            <translation>Exportar red a XML</translation>
        </message>
        <message>
            <source>Node degrees</source>
            <translation>Calcular grados de los nodos</translation>
        </message>
        <message>
            <source>Node elevation from DEM</source>
            <translation>Asignar cotas a nodos desde MDE</translation>
        </message>
        <message>
            <source>Node elevation from TIN (LandXML)</source>
            <translation>Asignar cotas a nodos desde TIN (LandXML)</translation>
        </message>
        <message>
            <source>Results from EPANET</source>
            <translation>Importar resultados de EPANET</translation>
        </message>
        <message>
            <source>Quality results</source>
            <translation>Resultados de calidad</translation>
        </message>
        <message>
            <source>Split lines at points</source>
            <translation>Dividir líneas en puntos</translation>
        </message>
        <message>
            <source>Update input layer</source>
            <translation>Actualizar capa de entrada</translation>
        </message>
        <message>
            <source>Algorithms</source>
            <translation>Algoritmos</translation>
        </message>
        <message>
            <location filename="../processes/wnt_assign_demand.py" line="108" />
            <source>Assignment layer</source>
            <translation>Capa de asignaciones</translation>
        </message>
        <message>
            <source>Audited Link layer</source>
            <translation>Capa de links auditada</translation>
        </message>
        <message>
            <source>Audited node layer</source>
            <translation>Capa de nodos auditada</translation>
        </message>
        <message>
            <source>Connection layer</source>
            <translation>Capa de conexiones</translation>
        </message>
        <message>
            <source>Coordinate reference system (CRS)</source>
            <translation>Sistema de referencia de coordenadas (SRC)</translation>
        </message>
        <message>
            <source>DEM raster layer input</source>
            <translation>Capa ráster MDE de entrada</translation>
        </message>
        <message>
            <source>Diameter field</source>
            <translation>Campo de diámetro</translation>
        </message>
        <message>
            <source>EPANET file</source>
            <translation>Archivo EPANET</translation>
        </message>
        <message>
            <source>EPANET lib</source>
            <translation>Biblioteca EPANET</translation>
        </message>
        <message>
            <source>EPANET links</source>
            <translation>Líneas EPANET</translation>
        </message>
        <message>
            <source>EPANET model file</source>
            <translation>Archivo de modelo EPANET</translation>
        </message>
        <message>
            <source>EPANET nodes</source>
            <translation>Nodos EPANET</translation>
        </message>
        <message>
            <source>EPANET scenario file</source>
            <translation>Archivo de escenario EPANET</translation>
        </message>
        <message>
            <source>EPANET version</source>
            <translation>Versión de EPANET</translation>
        </message>
        <message>
            <source>Edited assignment layer</source>
            <translation>Capa de asignaciones editada</translation>
        </message>
        <message>
            <source>Elevation field</source>
            <translation>Campo de elevación</translation>
        </message>
        <message>
            <source>Elevation field.</source>
            <translation>Campo de elevación.</translation>
        </message>
        <message>
            <source>Existing EPANET model file</source>
            <translation>Archivo de modelo EPANET existente</translation>
        </message>
        <message>
            <source>Existing EPANET model file is required for this output mode</source>
            <translation>El archivo de modelo EPANET existente es obligatorio para este modo de salida</translation>
        </message>
        <message>
            <location filename="../processes/wnt_network_to_epanet.py" line="159" />
            <source>Existing EPANET model file is required for workflow A</source>
            <translation>El archivo de modelo EPANET existente es obligatorio para el flujo A</translation>
        </message>
        <message>
            <source>Field containing demand</source>
            <translation>Campo que contiene la demanda</translation>
        </message>
        <message>
            <source>Fire demand factor</source>
            <translation>Factor punta en incendio</translation>
        </message>
        <message>
            <source>Fire flow name field</source>
            <translation>Campo de nombre de caudal de incendio</translation>
        </message>
        <message>
            <source>Fire flow value</source>
            <translation>Caudal de incendio</translation>
        </message>
        <message>
            <source>First link layer input</source>
            <translation>Primera capa de links de entrada</translation>
        </message>
        <message>
            <source>First node layer input</source>
            <translation>Primera capa de nodos de entrada</translation>
        </message>
        <message>
            <source>Flow units</source>
            <translation>Unidades de caudal</translation>
        </message>
        <message>
            <source>Hydrant ID field</source>
            <translation>Campo ID de hidrante</translation>
        </message>
        <message>
            <source>Hydrant layer input</source>
            <translation>Capa de hidrantes de entrada</translation>
        </message>
        <message>
            <source>Hydrant pairs / fire scenarios layer</source>
            <translation>Capa de pares de hidrantes / escenarios de incendio</translation>
        </message>
        <message>
            <source>Hydrant pairs layer</source>
            <translation>Capa de pares de hidrantes</translation>
        </message>
        <message>
            <source>Input line layer</source>
            <translation>Capa de líneas de entrada</translation>
        </message>
        <message>
            <source>Input link layer</source>
            <translation>Capa de links de entrada</translation>
        </message>
        <message>
            <source>Input link vector layer</source>
            <translation>Capa vectorial de líneas de entrada</translation>
        </message>
        <message>
            <source>Input links layer</source>
            <translation>Capa de links de entrada</translation>
        </message>
        <message>
            <source>Input node layer</source>
            <translation>Capa de nodos de entrada</translation>
        </message>
        <message>
            <source>Input node vector layer</source>
            <translation>Capa vectorial de nodos de entrada</translation>
        </message>
        <message>
            <source>Input nodes layer</source>
            <translation>Capa de nodos de entrada</translation>
        </message>
        <message>
            <source>Input point layer</source>
            <translation>Capa de puntos de entrada</translation>
        </message>
        <message>
            <source>LandXML file</source>
            <translation>Archivo LandXML</translation>
        </message>
        <message>
            <source>LandXML network type</source>
            <translation>Tipo de red LandXML</translation>
        </message>
        <message>
            <source>Line vector layer input</source>
            <translation>Capa vectorial de líneas de entrada</translation>
        </message>
        <message>
            <source>Link mask (P-$$-S generates P-01-S)</source>
            <translation>Máscara de links (P-$$-S genera P-01-S)</translation>
        </message>
        <message>
            <source>Link numbering increment</source>
            <translation>Incremento de la numeración del link</translation>
        </message>
        <message>
            <source>Link numbering increment must be an integer different from 0</source>
            <translation>El incremento de la numeración del link debe ser un entero distinto de 0</translation>
        </message>
        <message>
            <source>Link quality results</source>
            <translation>Resultados de calidad en links</translation>
        </message>
        <message>
            <source>Link results</source>
            <translation>Resultados de links</translation>
        </message>
        <message>
            <source>Link type field</source>
            <translation>Campo de tipo de link</translation>
        </message>
        <message>
            <source>Links</source>
            <translation>Links de salida</translation>
        </message>
        <message>
            <source>Max distance</source>
            <translation>Distancia máxima</translation>
        </message>
        <message>
            <source>Max number of connections</source>
            <translation>Número máximo de conexiones</translation>
        </message>
        <message>
            <source>Maximum hydrant separation</source>
            <translation>Separación máxima entre hidrantes</translation>
        </message>
        <message>
            <source>Merged link layer</source>
            <translation>Capa de links fusionada</translation>
        </message>
        <message>
            <source>Merged node layer</source>
            <translation>Capa de nodos fusionada</translation>
        </message>
        <message>
            <source>Minimum node separation, otherwise merge them</source>
            <translation>Separación mínima entre nodos; si no se cumple, se fusionan</translation>
        </message>
        <message>
            <source>Network link layer</source>
            <translation>Capa de links de la red</translation>
        </message>
        <message>
            <source>Network links layer input</source>
            <translation>Capa de links de red de entrada</translation>
        </message>
        <message>
            <source>Network name</source>
            <translation>Nombre de red</translation>
        </message>
        <message>
            <source>Network names</source>
            <translation>Nombres de red</translation>
        </message>
        <message>
            <source>Network node layer</source>
            <translation>Capa de nodos de la red</translation>
        </message>
        <message>
            <source>Network node layer input</source>
            <translation>Capa de nodos de la red de entrada</translation>
        </message>
        <message>
            <source>Node degree layer</source>
            <translation>Capa de grados de nodo</translation>
        </message>
        <message>
            <source>Node elevation source</source>
            <translation>Añadir elevación a los nodos</translation>
        </message>
        <message>
            <source>Node mask (P-$$-S generates P-01-S)</source>
            <translation>Máscara de nodos (P-$$-S genera P-01-S)</translation>
        </message>
        <message>
            <source>Node numbering increment</source>
            <translation>Incremento de la numeración del nodo</translation>
        </message>
        <message>
            <source>Node numbering increment must be an integer different from 0</source>
            <translation>El incremento de la numeración del nodo debe ser un entero distinto de 0</translation>
        </message>
        <message>
            <source>Node quality results</source>
            <translation>Resultados de calidad en nodos</translation>
        </message>
        <message>
            <source>Node results</source>
            <translation>Resultados de nodos</translation>
        </message>
        <message>
            <source>Node vector layer input</source>
            <translation>Capa vectorial de nodos de entrada</translation>
        </message>
        <message>
            <source>Nodes</source>
            <translation>Nodos</translation>
        </message>
        <message>
            <source>Nodes with elevation layer</source>
            <translation>Capa de nodos con elevación</translation>
        </message>
        <message>
            <source>Number of first link</source>
            <translation>Número del primer link</translation>
        </message>
        <message>
            <source>Number of the first node</source>
            <translation>Número del primer nodo</translation>
        </message>
        <message>
            <source>Output format</source>
            <translation>Formato de salida</translation>
        </message>
        <message>
            <source>Output mode</source>
            <translation>Modo de salida</translation>
        </message>
        <message>
            <source>Output pipesizing file</source>
            <translation>Archivo pipesizing de salida</translation>
        </message>
        <message>
            <source>Output ppno file</source>
            <translation>Archivo PPNO de salida</translation>
        </message>
        <message>
            <source>PPNO pipe catalog file</source>
            <translation>Archivo de catálogo de tuberías PPNO</translation>
        </message>
        <message>
            <source>Peak demand factor</source>
            <translation>Factor punta de demanda</translation>
        </message>
        <message>
            <source>Pipe group field</source>
            <translation>Campo de grupo de tuberías</translation>
        </message>
        <message>
            <source>Pipe series field</source>
            <translation>Campo de serie de tubería</translation>
        </message>
        <message>
            <source>Pipesizing pipe catalog file</source>
            <translation>Archivo de catálogo de tuberías pipesizing</translation>
        </message>
        <message>
            <source>Required fire pressure field</source>
            <translation>Campo de presión mínima en incendio</translation>
        </message>
        <message>
            <source>Required peak pressure field</source>
            <translation>Campo de presión mínima en caudal punta</translation>
        </message>
        <message>
            <source>Required pressure field</source>
            <translation>Campo de presión requerida</translation>
        </message>
        <message>
            <source>Result type</source>
            <translation>Tipo de resultado</translation>
        </message>
        <message>
            <source>Roughness field</source>
            <translation>Campo de rugosidad</translation>
        </message>
        <message>
            <source>Second link layer input</source>
            <translation>Segunda capa de links de entrada</translation>
        </message>
        <message>
            <source>Second node layer input</source>
            <translation>Segunda capa de nodos de entrada</translation>
        </message>
        <message>
            <location filename="../processes/wnt_assign_demand.py" line="89" />
            <source>Source demand fields</source>
            <translation>Campos de demanda de origen</translation>
        </message>
        <message>
            <location filename="../processes/wnt_assign_demand.py" line="82" />
            <source>Source layer</source>
            <translation>Capa de origen</translation>
        </message>
        <message>
            <source>Split line layer</source>
            <translation>Capa de líneas partidas</translation>
        </message>
        <message>
            <source>Subnetwork link layer</source>
            <translation>Capa de links de subred</translation>
        </message>
        <message>
            <source>Surface name</source>
            <translation>Nombre de superficie</translation>
        </message>
        <message>
            <source>Surface name (if empty, first found)</source>
            <translation>Nombre de la superficie (si se deja vacío, se usa la primera)</translation>
        </message>
        <message>
            <location filename="../processes/wnt_elevation_from_tin.py" line="104" />
            <source>Surface names</source>
            <translation>Nombres de superficie</translation>
        </message>
        <message>
            <location filename="../processes/wnt_assign_demand.py" line="99" />
            <source>Target layer</source>
            <translation>Capa de destino</translation>
        </message>
        <message>
            <location filename="../processes/wnt_assign_demand.py" line="114" />
            <source>Target with demands layer</source>
            <translation>Capa de destino con demandas</translation>
        </message>
        <message>
            <source>Tolerance</source>
            <translation>Tolerancia</translation>
        </message>
        <message>
            <source>Trivial Graph Format file</source>
            <translation>Archivo en formato TGF</translation>
        </message>
        <message>
            <source>Updated assignment layer</source>
            <translation>Capa de asignaciones actualizada</translation>
        </message>
        <message>
            <source>Updated target layer</source>
            <translation>Capa de destino actualizada</translation>
        </message>
        <message>
            <source>Version id</source>
            <translation>Id de versión</translation>
        </message>
        <message>
            <source>WNT model type</source>
            <translation>Tipo de modelo WNT</translation>
        </message>
        <message>
            <location filename="../processes/wnt_network_to_epanet.py" line="107" />
            <source>Workflow</source>
            <translation>Flujo de trabajo</translation>
        </message>
        <message>
            <source>XML file</source>
            <translation>Archivo XML</translation>
        </message>
        <message>
            <source>Assign demand</source>
            <translation>Asignar demanda</translation>
        </message>
        <message>
            <source>Configure EPANET lib</source>
            <translation>Configurar biblioteca EPANET</translation>
        </message>
        <message>
            <source>Connect by distance</source>
            <translation>Conectar por distancia</translation>
        </message>
        <message>
            <source>Demand to epanet scenario file (.scn)</source>
            <translation>Exportar demandas a escenario de EPANET (.scn)</translation>
        </message>
        <message>
            <source>Network from EPANET file</source>
            <translation>Importar red desde EPANET</translation>
        </message>
        <message>
            <source>Network from lines</source>
            <translation>Crear red a partir de líneas</translation>
        </message>
        <message>
            <source>Network to graph file</source>
            <translation>Exportar red a grafo</translation>
        </message>
        <message>
            <source>Network to pressure pipe optimization data file (.ext)</source>
            <translation>Exportar red a PPNO (.ext)</translation>
        </message>
        <message>
            <source>Pipe properties to EPANET scenario file (.scn)</source>
            <translation>Exportar propiedades de tuberías a escenario de EPANET (.scn)</translation>
        </message>
        <message>
            <source>Toolkit configuration file</source>
            <translation>Archivo de configuración del toolkit</translation>
        </message>
        <message>
            <source>Update assignment</source>
            <translation>Actualizar asignación</translation>
        </message>
        <message>
            <source>Validate</source>
            <translation>Validar</translation>
        </message>
        <message>
            <source>&lt;p&gt;Imports pipe networks from a LandXML 1.2 file.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Creates WNT node and link layers for pressure, sanitary and storm networks.&lt;/li&gt;
&lt;li&gt;Network names are written as a comma or semicolon separated list. If empty, all networks are loaded.&lt;/li&gt;
&lt;li&gt;Uses the coordinate reference system stored in the LandXML file when available.&lt;/li&gt;
&lt;/ul&gt;
        </source>
            <translation>&lt;p&gt;Importa redes de tuberías desde un archivo LandXML 1.2.&lt;/p&gt;
&lt;ul&gt;
&lt;li&gt;Crea capas WNT de nodos y links para redes a presión, de saneamiento y pluviales.&lt;/li&gt;
&lt;li&gt;Los nombres de red se escriben en una lista separada por comas o puntos y comas. Si se deja vacía, se cargan todas las redes.&lt;/li&gt;
&lt;li&gt;Utiliza el sistema de referencia de coordenadas almacenado en el archivo LandXML cuando está disponible.&lt;/li&gt;
&lt;/ul&gt;
        </translation>
        </message>
        <message>
            <source>Network from LandXML file</source>
            <translation>Importar red desde LandXML</translation>
        </message>
    </context>
</TS>
