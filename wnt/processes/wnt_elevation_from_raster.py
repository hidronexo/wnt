"""Set node elevations from a raster DEM."""

from math import isfinite

from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterField
                      )
from .base import (OUTPUT_MODE_NEW, OUTPUT_MODE_UPDATE, OUTPUT_MODE_OPTIONS,
                   WntProcessingAlgorithm, field_index, missing_fields,
                   set_progress, update_layer_attributes)
from .messages import crs as log_crs
from .messages import error, finish, info, start

class ElevationFromRasterAlgorithm(WntProcessingAlgorithm):
    """
    Set the node elevation from a DEM in raster format.
    """

    # DEFINE CONSTANTS
    INPUT_NODES = 'INPUT_NODES'
    INPUT_DEM = 'INPUT_DEM'
    FIELD_ELEVATION = 'FIELD_ELEVATION'
    OUTPUT_MODE = 'OUTPUT_MODE'
    OUTPUT = 'OUTPUT'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return ElevationFromRasterAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'elevation_from_raster'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Node elevation from DEM')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Modify')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to.
        """
        return 'modify'

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr('''<p>Sets node elevations from a raster DEM.</p>
<ul>
<li>Reads elevation values from the DEM at each node position.</li>
<li>Writes the values to the selected elevation field.</li>
<li>Nodes outside the raster extent are reported as skipped and kept unchanged.</li>
<li>Can create a new output layer or update the input node layer.</li>
</ul>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # ADD THE INPUT SOURCES
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NODES,
                self.tr('Node vector layer input'),
                types=[QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_ELEVATION,
                self.tr('Elevation field.'),
                None,
                self.INPUT_NODES,
                type=QgsProcessingParameterField.Numeric
                )
            )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_DEM,
                self.tr('DEM raster layer input')
                )
            )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OUTPUT_MODE,
                self.tr('Output mode'),
                options=[self.tr(option) for option in OUTPUT_MODE_OPTIONS],
                defaultValue=OUTPUT_MODE_NEW,
                optional=False
                )
            )

        #ADD THE OUTPUT SINK
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Nodes with elevation layer'),
                optional=True
                )
            )

    def processAlgorithm(self, parameters, context, feedback):
        """
        RUN PROCESS
        """

        # INPUT
        output_mode = self.parameterAsEnum(parameters, self.OUTPUT_MODE, context)
        if output_mode == OUTPUT_MODE_UPDATE:
            nodelayer = self.parameterAsVectorLayer(parameters, self.INPUT_NODES, context)
        else:
            nodelayer = self.parameterAsSource(parameters, self.INPUT_NODES, context)
        demlayer = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        efield = self.parameterAsString(parameters, self.FIELD_ELEVATION, context)
        from .base import validate_terrain_target
        validate_terrain_target(nodelayer, efield)

        missing = missing_fields(nodelayer, [efield])
        if missing:
            error(feedback, "Node layer is missing required fields: " + ", ".join(missing))

        # CHECK CRS
        crs = nodelayer.sourceCrs()
        if crs == demlayer.crs():

            # SEND INFORMATION TO THE USER
            start(feedback, self.displayName())
            log_crs(feedback, crs)
        else:
            error(feedback, "Layers have different CRS")

        if output_mode == OUTPUT_MODE_NEW:
            # OUTPUT
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                nodelayer.fields(),
                nodelayer.wkbType(),
                nodelayer.sourceCrs()
                )
        else:
            sink = None
            dest_id = getattr(nodelayer, 'id', lambda: self.INPUT_NODES)()

        # MAIN LOOP READ/WRITE POINTS
        pcnt = 0
        scnt = 0
        total_nodes = nodelayer.featureCount()
        provider = demlayer.dataProvider()
        elevation_index = field_index(nodelayer.fields(), efield)
        updates = {}

        def valid_sample(value):
            if value is None:
                return False
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return False
            if not isfinite(numeric):
                return False
            try:
                nodata = provider.sourceNoDataValue(1)
            except (AttributeError, TypeError):
                nodata = None
            return nodata is None or numeric != nodata

        for processed, feat in enumerate(nodelayer.getFeatures(), start=1):
            if feedback.isCanceled():
                return {}

            val, res = provider.sample(feat.geometry().asPoint(), 1)
            if res and valid_sample(val):
                pcnt += 1
                if output_mode == OUTPUT_MODE_UPDATE:
                    updates[feat.id()] = {elevation_index: val}
                else:
                    feat[efield] = val
            else:
                scnt += 1
            if output_mode == OUTPUT_MODE_NEW:
                sink.addFeature(feat, QgsFeatureSink.FastInsert)

            # SHOW PROGRESS
            if processed % 100 == 0 or processed == total_nodes:
                set_progress(feedback, 0, 100, processed, total_nodes)

        if output_mode == OUTPUT_MODE_UPDATE:
            try:
                update_layer_attributes(nodelayer, updates)
            except RuntimeError as exc:
                error(feedback, str(exc))

        info(feedback, "Processed nodes", pcnt)
        info(feedback, "Skipped nodes", scnt)
        info(feedback, "Output mode", OUTPUT_MODE_OPTIONS[output_mode])
        finish(feedback)

        # OUTPUT
        return {self.OUTPUT: dest_id}
