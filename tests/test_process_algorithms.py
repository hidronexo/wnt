"""Execution tests for selected Processing algorithms."""

import json
import xml.etree.ElementTree as ET
import pytest

pytest.importorskip("qgis")
from qgis.core import (QgsGeometry, QgsLineString, QgsMultiLineString, QgsPoint,
                       QgsPointXY, QgsProcessingException)

from wnt.processes import messages
from wnt.processes.wnt_assign_demand import AssignDemandAlgorithm
from wnt.processes.wnt_config_toolkit import ConfigToolkitAlgorithm
from wnt.processes.wnt_network_to_graph import NetworkToGraphAlgorithm
from wnt.processes.wnt_classify import ClassifyAlgorithm, topology_value
from wnt.processes.wnt_connect_by_distance import ConnectByDistanceAlgorithm
from wnt.processes.wnt_elevation_from_raster import ElevationFromRasterAlgorithm
from wnt.processes.wnt_elevation_from_tin import ElevationFromTINAlgorithm
from wnt.processes.wnt_network_to_epanet import NetworkToEpanetAlgorithm
from wnt.processes.wnt_network_to_xml import NetworkToXmlAlgorithm
from wnt.processes.wnt_hydrant_pairs import HydrantPairsAlgorithm
from wnt.processes.wnt_network_from_landxml import NetworkFromLandXMLAlgorithm
from wnt.processes.wnt_network_from_xml import NetworkFromXmlAlgorithm
from wnt.processes.wnt_merge_networks import MergeNetworksAlgorithm, aligned_feature
from wnt.processes.wnt_network_from_epanet import NetworkFromEpanetAlgorithm
from wnt.processes.wnt_network_from_lines import NetworkFromLinesAlgorithm
from wnt.processes.wnt_node_degrees import NodeDegreesAlgorithm
from wnt.processes.wnt_network_to_ppno import NetworkToPpnoAlgorithm
from wnt.processes.wnt_network_to_pipesizing import NetworkToPipesizingAlgorithm
from wnt.processes.wnt_results_from_epanet import ResultsFromEpanetAlgorithm
from wnt.processes.wnt_demand_to_epanet_scenario import DemandToEpanetScenarioAlgorithm
from wnt.processes.wnt_pipe_properties_to_epanet_scenario import PipePropertiesToEpanetScenarioAlgorithm
from wnt.processes.wnt_split_lines_at_points import SplitLinesAtPointsAlgorithm
from wnt.processes.wnt_update_assignment import UpdateAssignmentAlgorithm
from wnt.processes.wnt_validate import ValidateAlgorithm
from wnt.utils.utils_core import WntLink, WntNetwork, WntNode
from wnt.utils.utils_epanet_api import (
    constants_for_version,
    EpanetConfigurationError,
    EpanetError,
    format_elapsed_time,
    EpanetToolkit,
    ToolkitInfo,
)

from .utilities import get_qgis_app


QGIS_APP = get_qgis_app()


pytestmark = pytest.mark.qgis


class FakeCrs:
    def __init__(self, authid="EPSG:25830"):
        self._authid = authid

    def authid(self):
        return self._authid

    def __eq__(self, other):
        return isinstance(other, FakeCrs) and self._authid == other._authid


class FakeFields(list):
    def lookupField(self, name):
        for index, field in enumerate(self):
            if getattr(field, "name", lambda: None)() == name:
                return index
        return -1

    def names(self):
        return [field.name() for field in self]


class FakeNamedField:
    def __init__(self, name):
        self._name = name.name() if hasattr(name, "name") else name

    def name(self):
        return self._name

    def setName(self, name):
        self._name = name


def fake_fields(*names):
    return FakeFields(FakeNamedField(name) for name in names)


class FakeFeature:
    def __init__(self, attrs, geometry=None, fid=0):
        self._attrs = dict(attrs)
        self._attributes = list(attrs.values())
        self._geometry = geometry
        self._fid = fid

    def __getitem__(self, key):
        return self._attrs[key]

    def __setitem__(self, key, value):
        self._attrs[key] = value

    def attributes(self):
        return list(self._attributes)

    def setAttributes(self, attrs):
        self._attributes = list(attrs)

    def geometry(self):
        return self._geometry

    def setGeometry(self, geometry):
        self._geometry = geometry

    def id(self):
        return self._fid

    def fields(self):
        return FakeFields(FakeNamedField(name) for name in self._attrs)


class FakeSource:
    def __init__(self, features, fields=None, crs=None, wkb_type=1, name="example"):
        self._features = features
        for index, feature in enumerate(self._features):
            if getattr(feature, "_fid", None) == 0:
                feature._fid = index
        self._fields = fields or FakeFields()
        self._crs = crs or FakeCrs()
        self._wkb_type = wkb_type
        self._name = name

    def getFeatures(self, *args):
        return iter(self._features)

    def featureCount(self):
        return len(self._features)

    def fields(self):
        return FakeFields(self._fields)

    def sourceCrs(self):
        return self._crs

    def wkbType(self):
        return self._wkb_type

    def sourceName(self):
        return self._name

    def name(self):
        return self._name


class FakeSink:
    def __init__(self):
        self.features = []
        self.crs = None
        self.fields = None

    def addFeature(self, feature, *args):
        self.features.append(feature)

    def addFeatures(self, features, *args):
        self.features.extend(features)


class FakeLayerDetails:
    def __init__(self):
        self.name = None


class FakeProcessingContext:
    def __init__(self):
        self.layer_details = {}

    def layerToLoadOnCompletionDetails(self, layer_id):
        return self.layer_details.setdefault(layer_id, FakeLayerDetails())


class FakeOutputFeature:
    def __init__(self, *args):
        self.geometry_value = None
        self.attributes_value = None
        self._attrs = {}

    def setGeometry(self, geometry):
        self.geometry_value = geometry

    def setAttributes(self, attrs):
        self.attributes_value = list(attrs)

    def __getitem__(self, key):
        return self._attrs[key]

    def __setitem__(self, key, value):
        self._attrs[key] = value


class FakeFeedback:
    def __init__(self, canceled=False):
        self.canceled = canceled
        self.info = []
        self.errors = []
        self.fatal_errors = []
        self.progress = []

    def pushInfo(self, text):
        self.info.append(text)

    def reportError(self, text, fatalError=False):
        self.errors.append(text)
        self.fatal_errors.append(fatalError)

    def setProgress(self, value):
        self.progress.append(value)

    def isCanceled(self):
        return self.canceled


def bind_common_parameters(monkeypatch, algorithm, sources=None, fields=None, files=None, enums=None):
    sources = sources or {}
    fields = fields or {}
    files = files or {}
    enums = enums or {}
    sinks = {}

    monkeypatch.setattr(
        algorithm,
        "parameterAsSource",
        lambda parameters, name, context: sources[name],
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsRasterLayer",
        lambda parameters, name, context: sources.get(name),
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsFields",
        lambda parameters, name, context: fields[name]
        if isinstance(fields[name], list)
        else [fields[name]],
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsString",
        lambda parameters, name, context: fields.get(name, ""),
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsInt",
        lambda parameters, name, context: fields[name],
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsDouble",
        lambda parameters, name, context: fields[name],
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsBool",
        lambda parameters, name, context: fields.get(name, False),
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsEnum",
        lambda parameters, name, context: enums.get(name, 0),
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsEnums",
        lambda parameters, name, context: enums.get(name, []),
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsFile",
        lambda parameters, name, context: str(files[name]) if name in files else "",
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsFileOutput",
        lambda parameters, name, context: str(files[name]),
    )
    monkeypatch.setattr(
        algorithm,
        "parameterAsCrs",
        lambda parameters, name, context: fields.get(name, FakeCrs()),
    )

    def parameter_as_sink(parameters, name, context, *args, **kwargs):
        sink = FakeSink()
        sink.crs = kwargs.get("crs") or (args[2] if len(args) > 2 else None)
        sink.fields = args[0] if args else None
        sinks[name] = sink
        return sink, f"{name}_id"

    monkeypatch.setattr(algorithm, "parameterAsSink", parameter_as_sink)
    return sinks


class FakePoint:
    def __init__(self, x, y, z=None):
        self._x = x
        self._y = y
        self._z = z

    def x(self):
        return self._x

    def y(self):
        return self._y

    def z(self):
        return self._z if self._z is not None else float("nan")

    def distance(self, other):
        return ((self._x - other.x()) ** 2 + (self._y - other.y()) ** 2) ** 0.5


class FakeLineGeometry:
    def __init__(self, distance):
        self._distance = distance

    def length(self):
        return self._distance


class FakeGeometry:
    def __init__(self, x, y, wkt=None, polyline=None, multipolyline=None):
        self._point = FakePoint(x, y)
        self._wkt = wkt
        self._polyline = polyline
        self._multipolyline = multipolyline

    def asPoint(self):
        return self._point

    def asPolyline(self):
        return self._polyline or [self._point]

    def asMultiPolyline(self):
        return self._multipolyline or []

    def shortestLine(self, other):
        return FakeLineGeometry(self._point.distance(other.asPoint()))

    def distance(self, other):
        return self._point.distance(other.asPoint())

    def transform(self, transform):
        if self._polyline:
            self._polyline = [transform.transform(point) for point in self._polyline]
        if self._multipolyline:
            self._multipolyline = [
                [transform.transform(point) for point in part]
                for part in self._multipolyline
            ]
        else:
            self._point = transform.transform(self._point)

    def asWkt(self):
        return self._wkt or f"Point({self._point.x()} {self._point.y()})"


class FakeRasterProvider:
    def sample(self, point, band):
        if point.x() < 0:
            return None, False
        return point.x() + point.y(), True


class FakeRaster:
    def __init__(self, crs=None):
        self._crs = crs or FakeCrs()

    def crs(self):
        return self._crs

    def dataProvider(self):
        return FakeRasterProvider()


class FakeRasterWithProvider(FakeRaster):
    def __init__(self, provider):
        super().__init__()
        self._provider = provider

    def dataProvider(self):
        return self._provider


class FakeSpatialIndex:
    def __init__(self, features):
        self._features = list(features)

    def nearestNeighbor(self, point, count):
        ordered = sorted(
            self._features,
            key=lambda feature: point.distance(feature.geometry().asPoint()),
        )
        return [feature.id() for feature in ordered[:count]]


class FakeQgsGeometry:
    @staticmethod
    def fromPolyline(polyline):
        return FakeGeometry(0, 0, polyline=polyline)

    @staticmethod
    def fromPolylineXY(polyline):
        return FakeGeometry(0, 0, polyline=polyline)

    @staticmethod
    def fromPointXY(point):
        return FakeGeometry(point.x(), point.y())


def test_messages_cover_all_branches():
    feedback = FakeFeedback()

    messages.start(feedback, "Title")
    messages.finish(feedback)
    messages.info(feedback, "A", 1)
    messages.message(feedback, "plain")
    messages.crs(feedback, FakeCrs("EPSG:4326"))
    messages.crs(feedback, "")
    messages.warning(feedback, "careful")
    with pytest.raises(QgsProcessingException, match="ERROR: broken"):
        messages.error(feedback, "broken")

    assert "Process: Title" in feedback.info
    assert "CRS: EPSG:4326" in feedback.info
    assert "WARNING: CRS is not set" in feedback.info
    assert feedback.errors == ["ERROR: broken"]
    assert feedback.fatal_errors == [True]


def test_network_to_graph_writes_tgf_and_handles_cancel(monkeypatch, tmp_path):
    algorithm = NetworkToGraphAlgorithm()
    nodes = FakeSource([FakeFeature({"id": "N1"}), FakeFeature({"id": "N2"})], fields=fake_fields("id"))
    links = FakeSource([FakeFeature({"id": "L1", "start": "N1", "end": "N2"})], fields=fake_fields("id", "start", "end"))
    output = tmp_path / "network.tgf"
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        files={algorithm.OUTPUT: output},
    )

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    assert "0 N1" in output.read_text(encoding="utf-8")

    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}


def test_network_to_graph_rejects_undefined_link_nodes(monkeypatch, tmp_path):
    algorithm = NetworkToGraphAlgorithm()
    nodes = FakeSource([FakeFeature({"id": "N1"})], fields=fake_fields("id"))
    links = FakeSource(
        [FakeFeature({"id": "L1", "start": "N1", "end": "N2"})],
        fields=fake_fields("id", "start", "end"),
    )
    output = tmp_path / "invalid.tgf"
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        files={algorithm.OUTPUT: output},
    )

    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: undefined node links: L1"]
    assert not output.exists()


def test_node_degrees_writes_degree_field(monkeypatch):
    algorithm = NodeDegreesAlgorithm()
    nodes = FakeSource([FakeFeature({"id": "N1"}), FakeFeature({"id": "N2"})], fields=fake_fields("id"))
    links = FakeSource([FakeFeature({"id": "L1", "start": "N1", "end": "N2"})], fields=fake_fields("id", "start", "end"))
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
    )

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id"}
    assert [feature.attributes()[-1] for feature in sinks[algorithm.OUTPUT_NODES].features] == [1, 1]
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}


def test_classify_writes_topology_and_zone(monkeypatch):
    algorithm = ClassifyAlgorithm()
    links = FakeSource(
        [
            FakeFeature({"id": "T1", "start": "A", "end": "B"}),
            FakeFeature({"id": "T2", "start": "B", "end": "C"}),
            FakeFeature({"id": "M1", "start": "D", "end": "E"}),
            FakeFeature({"id": "M2", "start": "E", "end": "F"}),
            FakeFeature({"id": "M3", "start": "F", "end": "D"}),
        ],
        fields=fake_fields("id", "start", "end"),
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_LINES: links},
    )

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id"}
    classifications = [feature.attributes()[-2:] for feature in sinks[algorithm.OUTPUT_LINES].features]
    assert ["branched", 1] in classifications
    assert ["mesh", 2] in classifications
    assert sorted({zone for _, zone in classifications}) == [1, 2]
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}


def test_topology_value_falls_back_for_unknown_labels():
    assert topology_value("BRANCHED") == "branched"
    assert topology_value("MESHED") == "mesh"
    assert topology_value("RING") == "ring"
    assert topology_value(3) == "3"


def test_connect_by_distance_writes_nearest_connections_and_crs_error(monkeypatch):
    algorithm = ConnectByDistanceAlgorithm()
    monkeypatch.setattr("wnt.processes.wnt_connect_by_distance.QgsFeature", FakeOutputFeature)
    source = FakeSource(
        [
            FakeFeature({"id": "S1"}, FakeGeometry(0, 0)),
            FakeFeature({"id": "S2"}, FakeGeometry(10, 0)),
        ],
        fields=fake_fields("id"),
    )
    target = FakeSource(
        [
            FakeFeature({"id": "T1"}, FakeGeometry(1, 0)),
            FakeFeature({"id": "T2"}, FakeGeometry(3, 0)),
            FakeFeature({"id": "T3"}, FakeGeometry(20, 0)),
        ],
        fields=fake_fields("id"),
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_SOURCE: source, algorithm.INPUT_TARGET: target},
        fields={algorithm.MAX_CONNECTIONS: 1, algorithm.MAX_DISTANCE: 5},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT_CONNECTIONS: f"{algorithm.OUTPUT_CONNECTIONS}_id"}
    attrs = [feature.attributes_value for feature in sinks[algorithm.OUTPUT_CONNECTIONS].features]
    assert attrs == [["S1", "T1", 1.0, 1]]
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}

    bad_target = FakeSource([], crs=FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_SOURCE: source, algorithm.INPUT_TARGET: bad_target},
        fields={algorithm.MAX_CONNECTIONS: 1, algorithm.MAX_DISTANCE: 5},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]


def test_connect_by_distance_skips_self_when_source_and_target_are_same(monkeypatch):
    algorithm = ConnectByDistanceAlgorithm()
    monkeypatch.setattr("wnt.processes.wnt_connect_by_distance.QgsFeature", FakeOutputFeature)
    layer = FakeSource(
        [
            FakeFeature({"id": "N1"}, FakeGeometry(0, 0), fid=1),
            FakeFeature({"id": "N2"}, FakeGeometry(1, 0), fid=2),
        ],
        fields=fake_fields("id"),
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_SOURCE: layer, algorithm.INPUT_TARGET: layer},
        fields={algorithm.MAX_CONNECTIONS: 1, algorithm.MAX_DISTANCE: 2},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT_CONNECTIONS: f"{algorithm.OUTPUT_CONNECTIONS}_id"}
    attrs = [feature.attributes_value for feature in sinks[algorithm.OUTPUT_CONNECTIONS].features]
    assert attrs == [["N1", "N2", 1.0, 1], ["N2", "N1", 1.0, 1]]


def test_elevation_from_raster_processes_and_skips_nodes(monkeypatch):
    algorithm = ElevationFromRasterAlgorithm()
    nodes = FakeSource(
        [
            FakeFeature({"id": "N1", "elevation": 0}, FakeGeometry(1, 2)),
            FakeFeature({"id": "N2", "elevation": 0}, FakeGeometry(-1, 2)),
        ],
        fields=fake_fields("id", "elevation"),
    )
    raster = FakeRaster()
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_DEM: raster},
        fields={algorithm.FIELD_ELEVATION: "elevation"},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: f"{algorithm.OUTPUT}_id"}
    assert sinks[algorithm.OUTPUT].features[0]["elevation"] == 3
    assert sinks[algorithm.OUTPUT].features[1]["elevation"] == 0
    assert len(sinks[algorithm.OUTPUT].features) == 2
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}

    bad_raster = FakeRaster(FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_DEM: bad_raster},
        fields={algorithm.FIELD_ELEVATION: "elevation"},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]


def test_elevation_from_tin_interpolates_nodes(monkeypatch, tmp_path):
    algorithm = ElevationFromTINAlgorithm()
    nodes = FakeSource(
        [
            FakeFeature({"id": "N1", "elevation": 0}, FakeGeometry(0.25, 0.25)),
            FakeFeature({"id": "N2", "elevation": 0}, FakeGeometry(5, 5)),
        ]
    )
    xml = tmp_path / "surface.xml"
    xml.write_text(
        """
        <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
          <CoordinateSystem epsgCode="EPSG:4326" />
          <Surfaces>
            <Surface name="Ground">
              <Metadata />
              <Definition surfType="TIN">
                <Pnts>
                  <P id="1">0 0 1</P>
                  <P id="2">0 1 2</P>
                  <P id="3">1 0 3</P>
                </Pnts>
                <Faces><F>1 2 3</F></Faces>
              </Definition>
            </Surface>
          </Surfaces>
        </LandXML>
        """,
        encoding="utf-8",
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes},
        fields={algorithm.FIELD_ELEVATION: "elevation", algorithm.SURFACE_NAMES: "Ground"},
        files={algorithm.INPUT_TIN: xml},
    )

    feedback = FakeFeedback()
    result = algorithm.processAlgorithm({}, None, feedback)

    assert result == {algorithm.OUTPUT: f"{algorithm.OUTPUT}_id"}
    assert sinks[algorithm.OUTPUT].features[0]["elevation"] == pytest.approx(1.75)
    assert sinks[algorithm.OUTPUT].features[1]["elevation"] is None
    assert any("LandXML CRS EPSG:4326 differs" in line for line in feedback.info)
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}


def test_hydrant_pairs_writes_pairs_within_distance(monkeypatch):
    algorithm = HydrantPairsAlgorithm()
    monkeypatch.setattr("wnt.processes.wnt_hydrant_pairs.QgsFeature", FakeOutputFeature)
    monkeypatch.setattr("wnt.processes.wnt_hydrant_pairs.QgsPoint", lambda point: point)
    monkeypatch.setattr("wnt.processes.wnt_hydrant_pairs.QgsLineString", lambda points: points)
    hydrants = FakeSource(
        [
            FakeFeature({"hid": "H1"}, FakeGeometry(0, 0)),
            FakeFeature({"hid": "H2"}, FakeGeometry(3, 4)),
            FakeFeature({"hid": "H3"}, FakeGeometry(20, 0)),
        ]
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_HYDRANTS: hydrants},
        fields={algorithm.FIELD_ID: "hid", algorithm.MAX_DISTANCE: 5},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT_PAIRS: f"{algorithm.OUTPUT_PAIRS}_id"}
    assert [feature.attributes_value for feature in sinks[algorithm.OUTPUT_PAIRS].features] == [
        ["0", "H1", "H2", 5.0]
    ]
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}



def test_network_to_xml_writes_wnt_xml_and_validates_inputs(monkeypatch, tmp_path):
    algorithm = NetworkToXmlAlgorithm()
    output = tmp_path / "network.xml"
    node_fields = fake_fields("id", "type", "elevation", "swmm", "origin", "net_type")
    link_fields = fake_fields("id", "start", "end", "type", "length", "epanet", "material", "diameter")
    nodes = FakeSource(
        [
            FakeFeature(
                {
                    "id": "N1",
                    "type": "junction",
                    "elevation": 1.0,
                    "swmm": '{"invert_elevation":0.2}',
                    "origin": "StormNet",
                    "net_type": "storm",
                },
                FakeGeometry(0, 0),
            ),
            FakeFeature(
                {
                    "id": "N2",
                    "type": "outfall",
                    "elevation": 0.0,
                    "swmm": "{}",
                    "origin": "StormNet",
                    "net_type": "storm",
                },
                FakeGeometry(10, 0),
            ),
        ],
        fields=node_fields,
    )
    links = FakeSource(
        [
            FakeFeature(
                {
                    "id": "C1",
                    "start": "N1",
                    "end": "N2",
                    "type": "conduit",
                    "length": 10.5,
                    "epanet": '{"roughness":120}',
                    "material": "concrete",
                    "diameter": 600,
                },
                FakeGeometry(0, 0, "LineString(0 0, 10 0)"),
            )
        ],
        fields=link_fields,
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        fields={algorithm.NETWORK_NAME: "storm"},
        files={algorithm.OUTPUT: output},
        enums={
            algorithm.WNT_MODEL_TYPE: algorithm.WNT_MODEL_TYPES.index("swmm"),
            algorithm.OUTPUT_FORMAT: algorithm.FORMAT_WNT,
        },
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    loaded = WntNetwork().from_xml(output)
    assert loaded.xml_model_type == "swmm"
    assert loaded.nodes()[0].get_properties("swmm") == {"invert_elevation": 0.2}
    assert loaded.nodes()[0].get_properties("landxml")["origin"] == "StormNet"
    assert loaded.links()[0].get_length() == pytest.approx(10.5)
    assert loaded.links()[0].get_properties("epanet") == {"roughness": 120}
    assert loaded.links()[0].get_properties("landxml")["material"] == "concrete"

    bad_links = FakeSource([], fields=link_fields, crs=FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: bad_links},
        fields={algorithm.NETWORK_NAME: "storm"},
        files={algorithm.OUTPUT: output},
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]

    bad_nodes = FakeSource([], fields=fake_fields("id"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: bad_nodes, algorithm.INPUT_LINES: links},
        fields={algorithm.NETWORK_NAME: "storm"},
        files={algorithm.OUTPUT: output},
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Missing required fields: type"]


def test_network_to_xml_writes_landxml(monkeypatch, tmp_path):
    algorithm = NetworkToXmlAlgorithm()
    output = tmp_path / "network_landxml.xml"
    node_fields = fake_fields("id", "type", "elevation", "invert_elv", "rim_elv", "net_type")
    link_fields = fake_fields("id", "start", "end", "type", "length", "diameter", "material", "inv_start", "inv_end")
    nodes = FakeSource(
        [
            FakeFeature(
                {"id": "N1", "type": "manhole", "elevation": 2.0, "invert_elv": 1.0, "rim_elv": 3.0, "net_type": "storm"},
                FakeGeometry(0, 0),
            ),
            FakeFeature(
                {"id": "N2", "type": "outlet", "elevation": 1.0, "invert_elv": 0.5, "rim_elv": 2.5, "net_type": "storm"},
                FakeGeometry(10, 0),
            ),
        ],
        fields=node_fields,
    )
    links = FakeSource(
        [
            FakeFeature(
                {"id": "P1", "start": "N1", "end": "N2", "type": "conduit", "length": 10.0, "diameter": 300, "material": "PVC", "inv_start": 1.1, "inv_end": 0.7},
                FakeGeometry(0, 0, "LineString(0 0, 10 0)"),
            )
        ],
        fields=link_fields,
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        fields={algorithm.NETWORK_NAME: "Storm"},
        files={algorithm.OUTPUT: output},
        enums={
            algorithm.WNT_MODEL_TYPE: algorithm.WNT_MODEL_TYPES.index("swmm"),
            algorithm.OUTPUT_FORMAT: algorithm.FORMAT_LANDXML,
            algorithm.LANDXML_NETWORK_TYPE: algorithm.LANDXML_NETWORK_TYPES.index("storm"),
        },
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    root = ET.parse(output).getroot()
    namespace = {"lx": "http://www.landxml.org/schema/LandXML-1.2"}
    assert root.tag.endswith("LandXML")
    pipe_network = root.find(".//lx:PipeNetwork", namespace)
    assert pipe_network is not None
    assert pipe_network.get("name") == "Storm"
    assert pipe_network.get("pipeNetworkType") == "storm"
    assert root.find(".//lx:Struct[@name='N1']/lx:Center", namespace).text == "0 0"
    pipe = root.find(".//lx:Pipe[@name='P1']", namespace)
    assert pipe.get("material") == "PVC"
    assert pipe.find("lx:CircPipe", namespace).get("diameter") == "300"
    assert root.find(".//lx:Struct[@name='N1']/lx:Invert", namespace).get("elev") == "1.1"


def test_network_from_xml_loads_selected_xml_version(monkeypatch, tmp_path):
    xml_file = tmp_path / "network.xml"
    network = WntNetwork()
    node = WntNode("N1")
    node.set_type("JUNCTION")
    node.set_elevation(2.0)
    node.set_geometry((0, 0))
    node.get_properties("swmm")["invert_elevation"] = 0.5
    network.add_node(node)
    outfall = WntNode("N2")
    outfall.set_type("OUTFALL")
    outfall.set_geometry((1, 0))
    network.add_node(outfall)
    link = WntLink("C1", "N1", "N2")
    link.set_type("CONDUIT")
    link.set_length(1.0)
    link.set_geometry([(0, 0), (1, 0)])
    link.get_properties("landxml")["geom_shape"] = "circular"
    network.add_link(link)
    network.to_xml(xml_file, "v1", network_id="storm", model_type="swmm", crs="EPSG:25830")

    later = WntNetwork()
    later_node = WntNode("N3")
    later_node.set_type("JUNCTION")
    later_node.set_geometry((3, 0))
    later.add_node(later_node)
    later.to_xml(xml_file, "v2", network_id="storm", model_type="swmm", crs="EPSG:25830")

    algorithm = NetworkFromXmlAlgorithm()
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        files={algorithm.INPUT: xml_file},
        fields={algorithm.VERSION_ID: "v1"},
    )
    context = FakeProcessingContext()

    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    node_fields = sinks[algorithm.OUTPUT_NODES].fields.names()
    node_attrs = sinks[algorithm.OUTPUT_NODES].features[0].attributes()
    link_fields = sinks[algorithm.OUTPUT_LINES].fields.names()
    link_attrs = sinks[algorithm.OUTPUT_LINES].features[0].attributes()
    assert node_attrs[:3] == ["N1", "JUNCTION", 2.0]
    assert json.loads(node_attrs[node_fields.index("swmm")]) == {"invert_elevation": 0.5}
    assert link_attrs[:5] == ["C1", "N1", "N2", "CONDUIT", 1.0]
    assert json.loads(link_attrs[link_fields.index("landxml")]) == {"geom_shape": "circular"}
    assert context.layer_details[f"{algorithm.OUTPUT_NODES}_id"].name == "storm_nodes"

    sinks = bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: xml_file})
    result = algorithm.processAlgorithm({}, None, FakeFeedback())
    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert sinks[algorithm.OUTPUT_NODES].features[0].attributes()[0] == "N3"

def epanet_template_text():
    return (
        "[TITLE]\n[JUNCTIONS]\n[RESERVOIRS]\n[TANKS]\n[PIPES]\n[PUMPS]\n"
        "[VALVES]\n[COORDINATES]\n[VERTICES]\n[BACKDROP]\nDIMENSIONS 0 0 0 0\n[END]\n"
    )


def test_network_to_epanet_exports_file_and_rejects_crs(monkeypatch, tmp_path):
    algorithm = NetworkToEpanetAlgorithm()
    INPUT_TEMPLATE = tmp_path / "template.inp"
    output = tmp_path / "model.inp"
    INPUT_TEMPLATE.write_text(epanet_template_text(), encoding="latin-1")
    nodes = FakeSource(
        [
            FakeFeature({"id": "J1", "type": "JUNCTION", "elevation": 1}, FakeGeometry(0, 0)),
            FakeFeature({"id": "J2", "type": "RESERVOIR", "elevation": 2}, FakeGeometry(1, 0)),
        ]
    )
    links = FakeSource(
        [
            FakeFeature(
                {"id": "P1", "start": "J1", "end": "J2", "type": "PIPE", "length": 1.0},
                FakeGeometry(0, 0, "LineString(0 0, 1 0)"),
            )
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        files={algorithm.INPUT_TEMPLATE: INPUT_TEMPLATE, algorithm.OUTPUT: output},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    text = output.read_text(encoding="latin-1")
    assert "J1    1.0    0.0" in text
    assert "P1    J1    J2" in text
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}

    bad_links = FakeSource([], crs=FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: bad_links},
        files={algorithm.INPUT_TEMPLATE: INPUT_TEMPLATE, algorithm.OUTPUT: output},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]


def test_network_to_epanet_reports_duplicate_ids(monkeypatch, tmp_path):
    algorithm = NetworkToEpanetAlgorithm()
    template = tmp_path / "template.inp"
    output = tmp_path / "model.inp"
    template.write_text(epanet_template_text(), encoding="latin-1")
    nodes = FakeSource([
        FakeFeature({"id": "J1", "type": "JUNCTION", "elevation": 0}, FakeGeometry(0, 0)),
        FakeFeature({"id": "J1", "type": "JUNCTION", "elevation": 0}, FakeGeometry(1, 0)),
    ])
    links = FakeSource([], fields=fake_fields("id", "start", "end", "type", "length"))
    bind_common_parameters(
        monkeypatch, algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        files={algorithm.INPUT_TEMPLATE: template, algorithm.OUTPUT: output},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Duplicated node id: J1"]
    assert feedback.fatal_errors == [True]


def test_network_to_epanet_creates_file_from_scratch(monkeypatch, tmp_path):
    algorithm = NetworkToEpanetAlgorithm()
    output = tmp_path / "scratch.inp"
    nodes = FakeSource(
        [
            FakeFeature({"id": "J1", "type": "JUNCTION", "elevation": 1}, FakeGeometry(0, 0)),
            FakeFeature({"id": "J2", "type": "JUNCTION", "elevation": 2}, FakeGeometry(1, 0)),
        ]
    )
    links = FakeSource(
        [
            FakeFeature(
                    {"id": "P1", "start": "J1", "end": "J2", "type": "PIPE", "length": 1.0},
                FakeGeometry(0, 0, "LineString(0 0, 1 0)"),
            )
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        files={algorithm.OUTPUT: output},
        enums={
            algorithm.WORKFLOW: algorithm.WORKFLOW_SCRATCH,
            algorithm.EPANET_VERSION: 1,
            algorithm.FLOW_UNITS: algorithm.FLOW_UNIT_OPTIONS.index("CMH"),
        },
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    text = output.read_text(encoding="latin-1")
    assert "UNITS CMH" in text
    assert "DEMAND MODEL DDA" in text
    assert "J1    1.0    0.0" in text
    assert "J2    2.0    0.0" in text


def test_network_to_epanet_aborts_invalid_merged_network(monkeypatch, tmp_path):
    algorithm = NetworkToEpanetAlgorithm()
    output = tmp_path / "merged.inp"
    existing = tmp_path / "existing.inp"
    existing.write_text(
        "[JUNCTIONS]\n"
        "J1 0\n"
        "J2 0\n"
        "[PIPES]\n"
        "P1 J1 J2 1 100 100 0 Open\n"
        "[COORDINATES]\n"
        "J1 0 0\n"
        "J2 1 0\n"
        "[END]\n",
        encoding="latin-1",
    )
    nodes = FakeSource(
        [FakeFeature({"id": "J1", "type": "JUNCTION", "elevation": 1}, FakeGeometry(0, 0))]
    )
    links = FakeSource(
        [
            FakeFeature(
                {"id": "P2", "start": "J1", "end": "J2", "type": "PIPE", "length": 1.0},
                FakeGeometry(0, 0, "LineString(0 0, 1 0)"),
            )
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        files={algorithm.INPUT_EPANET: existing, algorithm.OUTPUT: output},
        enums={
            algorithm.WORKFLOW: algorithm.WORKFLOW_EXISTING,
            algorithm.EPANET_VERSION: 1,
            algorithm.FLOW_UNITS: algorithm.FLOW_UNIT_OPTIONS.index("CMH"),
        },
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)

    assert not output.exists()
    assert any("Merged EPANET network is not valid" in line for line in feedback.errors)


def test_epanet_minimal_templates_match_selected_versions():
    old_template = NetworkToEpanetAlgorithm._minimal_template_text("2.00.12", "LPS")
    new_template = NetworkToEpanetAlgorithm._minimal_template_text("2.2+", "GPM")

    assert "UNITS LPS" in old_template
    assert "DEMAND MODEL" not in old_template
    assert "UNITS GPM" in new_template
    assert "DEMAND MODEL DDA" in new_template

def test_network_from_epanet_imports_node_and_link_features(monkeypatch, tmp_path):
    algorithm = NetworkFromEpanetAlgorithm()
    inp = tmp_path / "example.inp"
    inp.write_text(
        """
        [JUNCTIONS]
        J1 1 5 PAT_J
        J2 2
        [DEMANDS]
        J1 7 PAT_ALT irrigation
        [EMITTERS]
        J2 0.25
        [RESERVOIRS]
        R1 100 PAT_R
        [TANKS]
        T1 10 1 0 5 15 0 VC1
        [QUALITY]
        J1 0.2
        T1 0.8
        [SOURCES]
        R1 CONCEN 1.5 PAT_SRC
        [MIXING]
        T1 MIXED 0.75
        [REACTIONS]
        BULK P1 -0.1
        WALL P1 -0.2
        TANK T1 -0.3
        [STATUS]
        P1 Closed
        PU1 Open
        [ENERGY]
        PUMP PU1 PRICE 0.15
        PUMP PU1 PATTERN ENERGY_PAT
        PUMP PU1 EFFIC EFF_CURVE
        [TAGS]
        NODE J1 DMA-A
        LINK P1 trunk main
        [COORDINATES]
        J1 0 0
        J2 1 0
        R1 2 0
        T1 3 0
        [PIPES]
        P1 J1 J2 1.0 100 120 0 Open
        [PUMPS]
        PU1 J2 R1 POWER 10 SPEED 1.2 PATTERN PAT_P
        [VALVES]
        V1 R1 T1 50 PRV 20 0.1
        [END]
        """,
        encoding="latin-1",
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        fields={algorithm.CRS: FakeCrs()},
        files={algorithm.INPUT: inp},
    )

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert context.layer_details[f"{algorithm.OUTPUT_NODES}_id"].name == "example_nodes"
    assert context.layer_details[f"{algorithm.OUTPUT_LINES}_id"].name == "example_links"
    nodes = {
        feature.attributes()[0]: feature.attributes()
        for feature in sinks[algorithm.OUTPUT_NODES].features
    }
    links = {
        feature.attributes()[0]: feature.attributes()
        for feature in sinks[algorithm.OUTPUT_LINES].features
    }
    assert nodes["J1"][:3] == ["J1", "JUNCTION", 1.0]
    assert json.loads(nodes["J1"][3]) == {
        "base_demand": "5",
        "demand_pattern": "PAT_J",
        "demands": [{"base_demand": "7", "demand_pattern": "PAT_ALT", "category": "irrigation"}],
        "emitter_coefficient": None,
        "initial_quality": "0.2",
        "source_pattern": None,
        "source_quality": None,
        "source_type": None,
        "tag": "DMA-A",
    }
    assert nodes["R1"][:3] == ["R1", "RESERVOIR", 100.0]
    assert json.loads(nodes["R1"][3]) == {
        "head_pattern": "PAT_R",
        "source_pattern": "PAT_SRC",
        "source_quality": "1.5",
        "source_type": "CONCEN",
        "initial_quality": None,
        "tag": None,
        "total_head": "100",
    }
    assert nodes["T1"][:3] == ["T1", "TANK", 10.0]
    assert json.loads(nodes["T1"][3]) == {
        "initial_level": "1",
        "initial_quality": "0.8",
        "max_level": "5",
        "min_level": "0",
        "min_volume": "0",
        "mixing_fraction": "0.75",
        "mixing_model": "MIXED",
        "diameter": "15",
        "source_pattern": None,
        "source_quality": None,
        "source_type": None,
        "tag": None,
        "tank_reaction_coeff": "-0.3",
        "volume_curve": "VC1",
    }
    assert links["P1"][:4] == ["P1", "J1", "J2", "PIPE"]
    assert json.loads(links["P1"][4]) == {
        "bulk_reaction_coeff": "-0.1",
        "diameter": "100",
        "initial_status": "Closed",
        "length": "1.0",
        "minor_loss": "0",
        "roughness": "120",
        "tag": "trunk main",
        "wall_reaction_coeff": "-0.2",
    }
    assert links["PU1"][:4] == ["PU1", "J2", "R1", "PUMP"]
    assert json.loads(links["PU1"][4]) == {
        "energy_pattern": "ENERGY_PAT",
        "energy_price": "0.15",
        "efficiency_curve": "EFF_CURVE",
        "head_curve": None,
        "initial_status": "Open",
        "pump_parameters": "POWER 10 SPEED 1.2 PATTERN PAT_P",
        "pump_pattern": "PAT_P",
        "pump_power": "10",
        "pump_speed": "1.2",
        "tag": None,
    }
    assert links["V1"][:4] == ["V1", "R1", "T1", "PRV"]
    assert json.loads(links["V1"][4]) == {
        "diameter": "50",
        "initial_status": None,
        "minor_loss": "0.1",
        "tag": None,
        "valve_setting": "20",
        "valve_type": "PRV",
    }
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}



def test_network_from_epanet_allows_missing_coordinates_in_output(monkeypatch, tmp_path):
    algorithm = NetworkFromEpanetAlgorithm()
    inp = tmp_path / "no_coordinates.inp"
    inp.write_text(
        "[JUNCTIONS]\nJ1 0\nJ2 0\n[PIPES]\nP1 J1 J2 1 100 120 0 Open\n[END]\n",
        encoding="latin-1",
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        fields={algorithm.CRS: FakeCrs()},
        files={algorithm.INPUT: inp},
    )

    result = algorithm.processAlgorithm({}, FakeProcessingContext(), FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert len(sinks[algorithm.OUTPUT_NODES].features) == 2
    assert len(sinks[algorithm.OUTPUT_LINES].features) == 1


def test_network_from_epanet_keeps_missing_version_dependent_json_keys_editable(monkeypatch, tmp_path):
    algorithm = NetworkFromEpanetAlgorithm()
    inp = tmp_path / "minimal.inp"
    inp.write_text(
        """
        [JUNCTIONS]
        J1 1
        [RESERVOIRS]
        R1 100
        [TANKS]
        T1 10
        [COORDINATES]
        J1 0 0
        R1 1 0
        T1 2 0
        [PIPES]
        P1 J1 R1 1.0 100 120
        [PUMPS]
        PU1 R1 T1 HEAD HC1
        [VALVES]
        V1 T1 J1 50 PRV
        [END]
        """,
        encoding="latin-1",
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        fields={algorithm.CRS: FakeCrs()},
        files={algorithm.INPUT: inp},
    )

    algorithm.processAlgorithm({}, FakeProcessingContext(), FakeFeedback())

    nodes = {
        feature.attributes()[0]: json.loads(feature.attributes()[3])
        for feature in sinks[algorithm.OUTPUT_NODES].features
    }
    links = {
        feature.attributes()[0]: json.loads(feature.attributes()[4])
        for feature in sinks[algorithm.OUTPUT_LINES].features
    }

    assert nodes["J1"] == {
        "base_demand": None,
        "demand_pattern": None,
        "demands": None,
        "emitter_coefficient": None,
        "initial_quality": None,
        "source_pattern": None,
        "source_quality": None,
        "source_type": None,
        "tag": None,
    }
    assert nodes["R1"] == {
        "head_pattern": None,
        "initial_quality": None,
        "source_pattern": None,
        "source_quality": None,
        "source_type": None,
        "tag": None,
        "total_head": "100",
    }
    assert nodes["T1"] == {
        "diameter": None,
        "initial_level": None,
        "initial_quality": None,
        "max_level": None,
        "min_level": None,
        "min_volume": None,
        "mixing_fraction": None,
        "mixing_model": None,
        "source_pattern": None,
        "source_quality": None,
        "source_type": None,
        "tag": None,
        "tank_reaction_coeff": None,
        "volume_curve": None,
    }
    assert links["P1"] == {
        "bulk_reaction_coeff": None,
        "diameter": "100",
        "initial_status": None,
        "length": "1.0",
        "minor_loss": None,
        "roughness": "120",
        "tag": None,
        "wall_reaction_coeff": None,
    }
    assert links["PU1"] == {
        "efficiency_curve": None,
        "energy_pattern": None,
        "energy_price": None,
        "head_curve": "HC1",
        "initial_status": None,
        "pump_parameters": "HEAD HC1",
        "pump_pattern": None,
        "pump_power": None,
        "pump_speed": None,
        "tag": None,
    }
    assert links["V1"] == {
        "diameter": "50",
        "initial_status": None,
        "minor_loss": None,
        "tag": None,
        "valve_setting": None,
        "valve_type": "PRV",
    }




def test_network_from_xml_reports_missing_landxml_pipe_networks(monkeypatch, tmp_path):
    algorithm = NetworkFromXmlAlgorithm()
    xml = tmp_path / "empty_landxml.xml"
    xml.write_text(
        '<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" />',
        encoding="utf-8",
    )
    bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: xml})

    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: No LandXML PipeNetwork definitions found"]


def test_network_from_landxml_rejects_other_xml_and_passes_selected_names(monkeypatch, tmp_path):
    algorithm = NetworkFromLandXMLAlgorithm()
    xml = tmp_path / "network.xml"
    xml.write_text("<wntNetworkStore />", encoding="utf-8")
    bind_common_parameters(
        monkeypatch,
        algorithm,
        fields={algorithm.NETWORK_NAMES: "Water; Storm"},
        files={algorithm.INPUT: xml},
    )

    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Invalid LandXML file: expected LandXML root"]

    xml.write_text(
        '<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" />',
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        algorithm,
        "_process_landxml",
        lambda xml_file, names, parameters, context, feedback: calls.append(
            (xml_file, names)
        ) or {"ok": True},
    )

    assert algorithm.processAlgorithm({}, None, feedback) == {"ok": True}
    assert calls == [(str(xml), ["Water", "Storm"])]

def test_network_from_xml_imports_landxml_features(monkeypatch, tmp_path):
    algorithm = NetworkFromXmlAlgorithm()
    extra_layers = {}
    monkeypatch.setattr(
        "wnt.processes.wnt_network_from_xml.add_memory_layer",
        lambda name, geometry, fields, crs, features, context=None: extra_layers.setdefault(
            name, [geometry, fields, features]
        ),
    )
    xml = tmp_path / "network.xml"
    xml.write_text(
        """
        <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
          <CoordinateSystem epsgCode="25830" />
          <PipeNetwork name="Storm" pipeNetType="storm">
            <Struct name=" S 1 (Storm) " desc="Inlet" elevSump="1" elevRim="3">
              <Center>10 20</Center>
              <Invert refPipe="P 1 (Storm)" elev="1.5" />
            </Struct>
            <Struct name="S2" desc="Outlet" elevSump="2" elevRim="5">
              <Center>11 21</Center>
              <Invert refPipe="P 1 (Storm)" elev="2.5" />
            </Struct>
            <Pipe name=" P 1 (Storm) " refStart=" S 1 (Storm) " refEnd=" S2 " length="12" slope="0.01">
              <CircPipe diameter="300" />
            </Pipe>
          </PipeNetwork>
          <PipeNetwork name="Agua potable">
            <Struct name="N1" elevSump="10">
              <Center>0 0</Center>
            </Struct>
            <Struct name="N2" elevSump="12">
              <Center>1 0</Center>
            </Struct>
            <Pipe name="WP1" refStart="N1" refEnd="N2" length="20" material="PVC">
              <CircPipe diameter="0.25" />
            </Pipe>
          </PipeNetwork>
        </LandXML>
        """,
        encoding="utf-8",
    )
    sinks = bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: xml})

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert context.layer_details[f"{algorithm.OUTPUT_NODES}_id"].name == "Storm_nodes"
    assert context.layer_details[f"{algorithm.OUTPUT_LINES}_id"].name == "Storm_links"
    assert sorted(extra_layers) == ["Agua_potable_links", "Agua_potable_nodes"]
    assert len(sinks[algorithm.OUTPUT_NODES].features) == 2
    node_attrs = {
        feature.attributes()[2]: feature.attributes()
        for feature in sinks[algorithm.OUTPUT_NODES].features
    }
    link_attrs = {
        feature.attributes()[2]: feature.attributes()
        for feature in sinks[algorithm.OUTPUT_LINES].features
    }
    assert node_attrs["S_1"][:7] == [
        "Storm",
        "storm",
        "S_1",
        "manhole",
        1.0,
        3.0,
        2.0,
    ]
    assert link_attrs["P_1"] == [
        "Storm",
        "storm",
        "P_1",
        "conduit",
        "S_1",
        "S2",
        12.0,
        "circular",
        0.3,
        0.0,
        0.013,
        1.5,
        2.5,
        -8.3333,
        0.5,
        0.5,
    ]
    water_link_attrs = extra_layers["Agua_potable_links"][2][0].attributes()
    assert water_link_attrs[:12] == [
        "Agua potable",
        "water",
        "WP1",
        "pipe",
        "N1",
        "N2",
        20.0,
        250.0,
        140.0,
        0.0,
        "open",
        "pvc",
    ]
    assert sinks[algorithm.OUTPUT_NODES].features[0].geometry().asWkt().startswith("Point")
    assert sinks[algorithm.OUTPUT_LINES].features[0].geometry().asWkt().startswith("LineString")
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}


def patch_lightweight_qgis_feature_classes(monkeypatch, module_name):
    monkeypatch.setattr(f"{module_name}.QgsFeature", FakeOutputFeature)
    monkeypatch.setattr(f"{module_name}.QgsField", lambda name, *args, **kwargs: FakeNamedField(name))
    monkeypatch.setattr(
        f"{module_name}.QgsFields",
        lambda fields=None: FakeFields(list(fields or [])),
    )
    monkeypatch.setattr(
        f"{module_name}.QgsPoint",
        lambda point, *args: point if not args else FakePoint(point, args[0]),
        raising=False,
    )
    monkeypatch.setattr(f"{module_name}.QgsLineString", lambda points: points, raising=False)


def test_assign_demand_accumulates_nearest_target(monkeypatch):
    algorithm = AssignDemandAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_assign_demand")
    monkeypatch.setattr("wnt.processes.wnt_assign_demand.QgsSpatialIndex", FakeSpatialIndex)
    FIELDS_SOURCE = FakeFields([FakeNamedField("id"), FakeNamedField("base"), FakeNamedField("fire")])
    target_fields = FakeFields([FakeNamedField("id")])
    sources = FakeSource(
        [
            FakeFeature({"id": "S1", "base": 1.0, "fire": 2.0}, FakeGeometry(0, 0), fid=1),
            FakeFeature({"id": "S2", "base": 3.0, "fire": 4.0}, FakeGeometry(10, 0), fid=2),
        ],
        fields=FIELDS_SOURCE,
    )
    targets = FakeSource(
        [
            FakeFeature({"id": "T1"}, FakeGeometry(1, 0), fid=101),
            FakeFeature({"id": "T2"}, FakeGeometry(9, 0), fid=102),
        ],
        fields=target_fields,
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_SOURCE: sources, algorithm.INPUT_TARGET: targets},
        fields={algorithm.FIELDS_SOURCE: ["base", "fire"]},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_ASSIGNMENTS: f"{algorithm.OUTPUT_ASSIGNMENTS}_id",
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
    }
    assignment_attrs = [
        feature.attributes_value for feature in sinks[algorithm.OUTPUT_ASSIGNMENTS].features
    ]
    node_attrs = [feature.attributes_value for feature in sinks[algorithm.OUTPUT_NODES].features]
    assert assignment_attrs == [["S1", "T1", 1.0, 2.0], ["S2", "T2", 3.0, 4.0]]
    assert node_attrs == [["T1", 1.0, 2.0], ["T2", 3.0, 4.0]]
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}

    bad_targets = FakeSource([], crs=FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_SOURCE: sources, algorithm.INPUT_TARGET: bad_targets},
        fields={algorithm.FIELDS_SOURCE: ["base"]},
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]


def test_assign_demand_rejects_geographic_crs_and_duplicate_target_ids(monkeypatch):
    algorithm = AssignDemandAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_assign_demand")
    monkeypatch.setattr("wnt.processes.wnt_assign_demand.QgsSpatialIndex", FakeSpatialIndex)
    geographic = FakeCrs("EPSG:4326")
    sources = FakeSource(
        [FakeFeature({"id": "S1", "base": 1.0}, FakeGeometry(0, 0))],
        fields=fake_fields("id", "base"),
        crs=geographic,
    )
    targets = FakeSource(
        [FakeFeature({"id": "T1"}, FakeGeometry(1, 0))],
        fields=fake_fields("id"),
        crs=geographic,
    )
    bind_common_parameters(
        monkeypatch, algorithm,
        sources={algorithm.INPUT_SOURCE: sources, algorithm.INPUT_TARGET: targets},
        fields={algorithm.FIELDS_SOURCE: ["base"]},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == [
        "ERROR: Use a projected CRS with linear units for distance-based operations"
    ]

    projected_sources = FakeSource(
        [FakeFeature({"id": "S1", "base": 1.0}, FakeGeometry(0, 0))],
        fields=fake_fields("id", "base"),
    )
    duplicate_targets = FakeSource(
        [
            FakeFeature({"id": "T1"}, FakeGeometry(1, 0), fid=1),
            FakeFeature({"id": "T1"}, FakeGeometry(2, 0), fid=2),
        ],
        fields=fake_fields("id"),
    )
    bind_common_parameters(
        monkeypatch, algorithm,
        sources={algorithm.INPUT_SOURCE: projected_sources, algorithm.INPUT_TARGET: duplicate_targets},
        fields={algorithm.FIELDS_SOURCE: ["base"]},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Target layer contains duplicate ids: T1"]


def test_update_assignment_updates_moved_target_and_errors(monkeypatch):
    algorithm = UpdateAssignmentAlgorithm()
    fields = FakeFields([FakeNamedField("source"), FakeNamedField("target"), FakeNamedField("base")])
    sources = FakeSource(
        [FakeFeature({"id": "S1", "base": 5.0}, FakeGeometry(0, 0))],
        fields=FakeFields([FakeNamedField("id"), FakeNamedField("base")]),
    )
    targets = FakeSource(
        [
            FakeFeature({"id": "T1", "base": 0.0}, FakeGeometry(1, 0)),
            FakeFeature({"id": "T2", "base": 0.0}, FakeGeometry(2, 0)),
        ],
        fields=FakeFields([FakeNamedField("id"), FakeNamedField("base")]),
    )
    assignments = FakeSource(
        [
            FakeFeature(
                {"source": "S1", "target": "T1", "base": 0.0},
                FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(2, 0)]),
            )
        ],
        fields=fields,
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_SOURCE: sources,
            algorithm.INPUT_TARGET: targets,
            algorithm.INPUT_ASSIGNMENTS: assignments,
        },
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_ASSIGNMENTS: f"{algorithm.OUTPUT_ASSIGNMENTS}_id",
        algorithm.OUTPUT_TARGETS: f"{algorithm.OUTPUT_TARGETS}_id",
    }
    assert sinks[algorithm.OUTPUT_ASSIGNMENTS].features[0]["target"] == "T2"
    assert [feature["base"] for feature in sinks[algorithm.OUTPUT_TARGETS].features] == [0, 5.0]
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}

    misplaced = FakeSource(
        [
            FakeFeature(
                {"source": "S1", "target": "T1", "base": 0.0},
                FakeGeometry(0, 0, polyline=[FakePoint(9, 9), FakePoint(1, 0)]),
            )
        ],
        fields=fields,
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_SOURCE: sources,
            algorithm.INPUT_TARGET: targets,
            algorithm.INPUT_ASSIGNMENTS: misplaced,
        },
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Source point misplaced: S1"]



def test_update_assignment_treats_null_demand_as_zero(monkeypatch):
    algorithm = UpdateAssignmentAlgorithm()
    fields = fake_fields("source", "target", "base")
    sources = FakeSource(
        [FakeFeature({"id": "S1", "base": None}, FakeGeometry(0, 0))],
        fields=fake_fields("id", "base"),
    )
    targets = FakeSource(
        [FakeFeature({"id": "T1", "base": 5.0}, FakeGeometry(1, 0))],
        fields=fake_fields("id", "base"),
    )
    assignments = FakeSource(
        [FakeFeature(
            {"source": "S1", "target": "T1", "base": None},
            FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(1, 0)]),
        )],
        fields=fields,
    )
    sinks = bind_common_parameters(
        monkeypatch, algorithm,
        sources={
            algorithm.INPUT_SOURCE: sources,
            algorithm.INPUT_TARGET: targets,
            algorithm.INPUT_ASSIGNMENTS: assignments,
        },
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result[algorithm.OUTPUT_TARGETS] == f"{algorithm.OUTPUT_TARGETS}_id"
    assert sinks[algorithm.OUTPUT_TARGETS].features[0]["base"] == 0.0


def test_update_assignment_validates_schema_and_geometry(monkeypatch):
    algorithm = UpdateAssignmentAlgorithm()
    sources = FakeSource(
        [FakeFeature({"id": "S1", "base": 1.0}, FakeGeometry(0, 0))],
        fields=FakeFields([FakeNamedField("id"), FakeNamedField("base")]),
    )
    targets = FakeSource(
        [FakeFeature({"id": "T1", "base": 0.0}, FakeGeometry(1, 0))],
        fields=FakeFields([FakeNamedField("id"), FakeNamedField("base")]),
    )
    missing_target = FakeSource(
        [FakeFeature({"source": "S1", "base": 0.0}, FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(1, 0)]))],
        fields=FakeFields([FakeNamedField("source"), FakeNamedField("base")]),
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_SOURCE: sources,
            algorithm.INPUT_TARGET: targets,
            algorithm.INPUT_ASSIGNMENTS: missing_target,
        },
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Assignment layer is missing required fields: target"]

    empty_geometry = FakeSource(
        [FakeFeature({"source": "S1", "target": "T1", "base": 0.0}, FakeGeometry(0, 0, polyline=[]))],
        fields=FakeFields([FakeNamedField("source"), FakeNamedField("target"), FakeNamedField("base")]),
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_SOURCE: sources,
            algorithm.INPUT_TARGET: targets,
            algorithm.INPUT_ASSIGNMENTS: empty_geometry,
        },
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Assignment geometry must be a LineString with at least two vertices"]


def test_split_lines_at_points_splits_and_keeps_original(monkeypatch):
    algorithm = SplitLinesAtPointsAlgorithm()

    points = FakeSource(
        [
            FakeFeature({"id": "P1"}, QgsGeometry.fromPointXY(QgsPointXY(1, 0))),
            FakeFeature({"id": "P2"}, QgsGeometry.fromPointXY(QgsPointXY(1.0001, 0))),
            FakeFeature({"id": "P3"}, QgsGeometry.fromPointXY(QgsPointXY(10, 10))),
        ]
    )
    lines = FakeSource(
        [
            FakeFeature({"id": "L1"}, QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(2, 0)])),
            FakeFeature({"id": "L2"}, QgsGeometry.fromPolylineXY([QgsPointXY(0, 1), QgsPointXY(2, 1)])),
        ]
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_POINTS: points, algorithm.INPUT_LINES: lines},
        fields={algorithm.TOLERANCE: 0.01},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: f"{algorithm.OUTPUT}_id"}
    assert len(sinks[algorithm.OUTPUT].features) == 3
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}

    bad_lines = FakeSource([], crs=FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_POINTS: points, algorithm.INPUT_LINES: bad_lines},
        fields={algorithm.TOLERANCE: 0.01},
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]


def test_merge_networks_merges_near_nodes_snaps_links_and_reports_counts(monkeypatch):
    algorithm = MergeNetworksAlgorithm()
    monkeypatch.setattr("wnt.processes.wnt_merge_networks.QgsFeature", FakeOutputFeature)
    node_fields_1 = FakeFields([FakeNamedField("id"), FakeNamedField("elevation")])
    node_fields_2 = FakeFields([FakeNamedField("id"), FakeNamedField("zone")])
    link_fields_1 = FakeFields([FakeNamedField("id"), FakeNamedField("start"), FakeNamedField("end")])
    link_fields_2 = FakeFields([FakeNamedField("id"), FakeNamedField("start"), FakeNamedField("end"), FakeNamedField("diameter")])
    n1 = FakeSource(
        [
            FakeFeature({"id": "N1", "elevation": 1}, QgsGeometry.fromPointXY(QgsPointXY(0, 0))),
            FakeFeature({"id": "N2", "elevation": 2}, QgsGeometry.fromPointXY(QgsPointXY(1, 0))),
        ],
        fields=node_fields_1,
    )
    n2 = FakeSource(
        [
            FakeFeature({"id": "N2B", "zone": "B"}, QgsGeometry.fromPointXY(QgsPointXY(1.005, 0))),
            FakeFeature({"id": "N3", "zone": "C"}, QgsGeometry.fromPointXY(QgsPointXY(3, 0))),
            ],
            fields=node_fields_2,
    )
    l1 = FakeSource(
        [
            FakeFeature(
                {"id": "L1", "start": "N1", "end": "N2"},
                QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]),
            )
        ],
        fields=link_fields_1,
    )
    l2 = FakeSource(
        [
            FakeFeature(
                {"id": "L2", "start": "N2B", "end": "N3", "diameter": 100},
                QgsGeometry.fromPolylineXY([QgsPointXY(1.005, 0), QgsPointXY(3, 0)]),
            )
        ],
        fields=link_fields_2,
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_NODES_1: n1,
            algorithm.INPUT_LINES_1: l1,
            algorithm.INPUT_NODES_2: n2,
            algorithm.INPUT_LINES_2: l2,
        },
        fields={algorithm.TOLERANCE: 0.01},
    )
    feedback = FakeFeedback()

    result = algorithm.processAlgorithm({}, None, feedback)

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert [feature.attributes_value for feature in sinks[algorithm.OUTPUT_NODES].features] == [
        ["N1", 1, None],
        ["N2", 2, None],
        ["N3", None, "C"],
    ]
    assert [feature.attributes_value for feature in sinks[algorithm.OUTPUT_LINES].features] == [
        ["L1", "N1", "N2", None],
        ["L2", "N2", "N3", 100],
    ]
    snapped = sinks[algorithm.OUTPUT_LINES].features[1].geometry_value.asPolyline()
    assert snapped[0].x() == pytest.approx(1.0)
    assert snapped[0].y() == pytest.approx(0.0)
    assert snapped[-1].x() == pytest.approx(3.0)
    assert "First network nodes: 2" in feedback.info
    assert "Second network nodes: 2" in feedback.info
    assert "Output nodes: 3" in feedback.info
    assert "First network links: 1" in feedback.info
    assert "Second network links: 1" in feedback.info
    assert "Output links: 2" in feedback.info
    assert "Connected nodes: 1" in feedback.info
    assert "Near merge nodes: 0" in feedback.info
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}

    bad = FakeSource([], crs=FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_NODES_1: n1,
            algorithm.INPUT_LINES_1: l1,
            algorithm.INPUT_NODES_2: bad,
            algorithm.INPUT_LINES_2: l2,
        },
        fields={algorithm.TOLERANCE: 0.01},
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]


def test_merge_networks_rejects_second_link_duplicate_id(monkeypatch):
    algorithm = MergeNetworksAlgorithm()
    node_fields = fake_fields("id")
    link_fields = fake_fields("id", "start", "end")
    n1 = FakeSource(
        [
            FakeFeature({"id": "N1"}, QgsGeometry.fromPointXY(QgsPointXY(0, 0))),
            FakeFeature({"id": "N2"}, QgsGeometry.fromPointXY(QgsPointXY(1, 0))),
        ],
        fields=node_fields,
    )
    n2 = FakeSource(
        [
            FakeFeature({"id": "N3"}, QgsGeometry.fromPointXY(QgsPointXY(2, 0))),
            FakeFeature({"id": "N4"}, QgsGeometry.fromPointXY(QgsPointXY(3, 0))),
        ],
        fields=node_fields,
    )
    l1 = FakeSource(
        [FakeFeature({"id": "L1", "start": "N1", "end": "N2"}, QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]))],
        fields=link_fields,
    )
    l2 = FakeSource(
        [FakeFeature({"id": "L1", "start": "N3", "end": "N4"}, QgsGeometry.fromPolylineXY([QgsPointXY(2, 0), QgsPointXY(3, 0)]))],
        fields=link_fields,
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_NODES_1: n1,
            algorithm.INPUT_LINES_1: l1,
            algorithm.INPUT_NODES_2: n2,
            algorithm.INPUT_LINES_2: l2,
        },
        fields={algorithm.TOLERANCE: 0.01},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Second network link ids already exist in first network: L1"]


def test_merge_networks_aborts_invalid_final_network(monkeypatch):
    algorithm = MergeNetworksAlgorithm()
    node_fields = fake_fields("id")
    link_fields = fake_fields("id", "start", "end")
    n1 = FakeSource(
        [
            FakeFeature({"id": "N1"}, QgsGeometry.fromPointXY(QgsPointXY(0, 0))),
            FakeFeature({"id": "N2"}, QgsGeometry.fromPointXY(QgsPointXY(1, 0))),
        ],
        fields=node_fields,
    )
    n2 = FakeSource(
        [FakeFeature({"id": "N3"}, QgsGeometry.fromPointXY(QgsPointXY(5, 0)))],
        fields=node_fields,
    )
    l1 = FakeSource(
        [
            FakeFeature(
                {"id": "L1", "start": "N1", "end": "N2"},
                QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]),
            )
        ],
        fields=link_fields,
    )
    l2 = FakeSource([], fields=link_fields)
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_NODES_1: n1,
            algorithm.INPUT_LINES_1: l1,
            algorithm.INPUT_NODES_2: n2,
            algorithm.INPUT_LINES_2: l2,
        },
        fields={algorithm.TOLERANCE: 0.01},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert any("orphan nodes: N3" in line for line in feedback.errors)


def test_merge_networks_rejects_second_link_endpoint_overlap_reversed(monkeypatch):
    algorithm = MergeNetworksAlgorithm()
    node_fields = fake_fields("id")
    link_fields = fake_fields("id", "start", "end")
    n1 = FakeSource(
        [
            FakeFeature({"id": "N1"}, QgsGeometry.fromPointXY(QgsPointXY(0, 0))),
            FakeFeature({"id": "N2"}, QgsGeometry.fromPointXY(QgsPointXY(1, 0))),
        ],
        fields=node_fields,
    )
    n2 = FakeSource(
        [
            FakeFeature({"id": "N3"}, QgsGeometry.fromPointXY(QgsPointXY(1.005, 0))),
            FakeFeature({"id": "N4"}, QgsGeometry.fromPointXY(QgsPointXY(0.005, 0))),
        ],
        fields=node_fields,
    )
    l1 = FakeSource(
        [FakeFeature({"id": "L1", "start": "N1", "end": "N2"}, QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]))],
        fields=link_fields,
    )
    l2 = FakeSource(
        [FakeFeature({"id": "L2", "start": "N3", "end": "N4"}, QgsGeometry.fromPolylineXY([QgsPointXY(1.005, 0), QgsPointXY(0.005, 0)]))],
        fields=link_fields,
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={
            algorithm.INPUT_NODES_1: n1,
            algorithm.INPUT_LINES_1: l1,
            algorithm.INPUT_NODES_2: n2,
            algorithm.INPUT_LINES_2: l2,
        },
        fields={algorithm.TOLERANCE: 0.01},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Second network links overlap first network links: L2 overlaps L1"]
    assert sinks == {}

def test_aligned_feature_fills_missing_fields(monkeypatch):
    monkeypatch.setattr("wnt.processes.wnt_merge_networks.QgsFeature", FakeOutputFeature)
    feature = FakeFeature({"id": "N1"}, FakeGeometry(0, 0))
    result = aligned_feature(feature, FakeFields([FakeNamedField("id"), FakeNamedField("missing")]))

    assert result.attributes_value == ["N1", None]


def test_network_from_lines_builds_node_and_link_outputs(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)
    fields = FakeFields([FakeNamedField("material")])
    lines = FakeSource(
        [
            FakeFeature(
                {"material": "PVC"},
                FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(1, 0)]),
                fid=11,
            ),
            FakeFeature(
                {"material": "DI"},
                FakeGeometry(1, 0, polyline=[FakePoint(1, 0), FakePoint(2, 0)]),
                fid=12,
            ),
        ],
        fields=fields,
        name="linestring_layer",
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
    )

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert [feature.attributes_value for feature in sinks[algorithm.OUTPUT_NODES].features] == [
        ["N1", "JUNCTION", 0.0],
        ["N2", "JUNCTION", 0.0],
        ["N3", "JUNCTION", 0.0],
    ]
    assert [feature.attributes_value[:5] for feature in sinks[algorithm.OUTPUT_LINES].features] == [
        ["L1", "N1", "N2", "PIPE", 1.0],
        ["L2", "N2", "N3", "PIPE", 1.0],
    ]
    assert context.layer_details[f"{algorithm.OUTPUT_NODES}_id"].name == "linestring_layer_nodes"
    assert context.layer_details[f"{algorithm.OUTPUT_LINES}_id"].name == "linestring_layer_links"
    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}


def test_network_from_lines_rejects_zero_numbering_increments(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    monkeypatch.setattr(
        algorithm,
        "parameterAsInt",
        lambda parameters, name, context: parameters[name],
    )

    valid = {
        algorithm.INCREMENT_NODE: 1,
        algorithm.INCREMENT_LINK: 1,
    }

    ok, message = algorithm.checkParameterValues(
        {**valid, algorithm.INCREMENT_NODE: 0},
        None,
    )
    assert not ok
    assert message == "Node numbering increment must be an integer different from 0"

    ok, message = algorithm.checkParameterValues(
        {**valid, algorithm.INCREMENT_LINK: 0},
        None,
    )
    assert not ok
    assert message == "Link numbering increment must be an integer different from 0"


def test_network_from_lines_reports_monotonic_progress(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)
    lines = FakeSource(
        [
            FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(1, 0)])),
            FakeFeature({}, FakeGeometry(1, 0, polyline=[FakePoint(1, 0), FakePoint(2, 0)])),
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
    )

    feedback = FakeFeedback()
    algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)

    assert feedback.progress
    assert feedback.progress == sorted(feedback.progress)
    assert feedback.progress[-1] == 100


def test_network_from_lines_splits_multipart_and_uses_z_elevations(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)
    fields = FakeFields([FakeNamedField("material")])
    lines = FakeSource(
        [
            FakeFeature(
                {"material": "PVC"},
                FakeGeometry(
                    0,
                    0,
                    multipolyline=[
                        [FakePoint(0, 0, 10.0), FakePoint(1, 0, 11.0)],
                        [FakePoint(1, 0, 11.0004), FakePoint(2, 0, 12.0)],
                    ],
                ),
                fid=11,
            ),
        ],
        fields=fields,
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
        enums={algorithm.ELEVATION_SOURCE: 1},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert [feature.attributes_value for feature in sinks[algorithm.OUTPUT_NODES].features] == [
        ["N1", "JUNCTION", 10.0],
        ["N2", "JUNCTION", pytest.approx(11.0002)],
        ["N3", "JUNCTION", 12.0],
    ]
    assert [feature.attributes_value for feature in sinks[algorithm.OUTPUT_LINES].features] == [
        ["L1", "N1", "N2", "PIPE", 1.0, "PVC"],
        ["L2", "N2", "N3", "PIPE", 1.0, "PVC"],
    ]


def test_network_from_lines_writes_link_type_degree_and_topology(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)
    fields = FakeFields([
        FakeNamedField("link_type"), FakeNamedField("material"),
        FakeNamedField("id"), FakeNamedField("length"),
    ])
    lines = FakeSource(
        [
            FakeFeature(
                {"link_type": "VALVE", "material": "PVC", "id": "old-1", "length": 99},
                FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(1, 0)]),
            ),
            FakeFeature(
                {"link_type": "PUMP", "material": "DI", "id": "old-2", "length": 98},
                FakeGeometry(1, 0, polyline=[FakePoint(1, 0), FakePoint(2, 0)]),
            ),
        ],
        fields=fields,
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
            algorithm.LINK_TYPE_FIELD: "link_type",
            algorithm.ADD_NODE_DEGREE: True,
            algorithm.ADD_LINK_TOPOLOGY: True,
        },
    )

    feedback = FakeFeedback()
    algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)

    assert [feature.attributes_value for feature in sinks[algorithm.OUTPUT_NODES].features] == [
        ["N1", "JUNCTION", 0.0, 1],
        ["N2", "JUNCTION", 0.0, 2],
        ["N3", "JUNCTION", 0.0, 1],
    ]
    assert [feature.attributes_value[:7] for feature in sinks[algorithm.OUTPUT_LINES].features] == [
        ["L1", "N1", "N2", "VALVE", 1.0, "branched", 1],
        ["L2", "N2", "N3", "PUMP", 1.0, "branched", 1],
    ]
    link_field_names = sinks[algorithm.OUTPUT_LINES].fields.names()
    assert "zone" in link_field_names
    assert "zones" not in link_field_names
    assert "id_src" in link_field_names
    assert "length_src" in link_field_names
    assert len(link_field_names) == len(set(link_field_names))
    assert "Link type field: link_type" in feedback.info
    assert "Add node_degree: True" in feedback.info
    assert "Add topology/zone: True" in feedback.info


def test_network_from_lines_reprojects_to_selected_crs(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)

    class FakeTransform:
        def __init__(self, source, target, project):
            self.source = source
            self.target = target
            self.project = project

        def transform(self, point):
            z = point.z() if hasattr(point, "z") else None
            return FakePoint(point.x() + 10, point.y() + 20, z)

    class FakeProject:
        @staticmethod
        def instance():
            return object()

    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsCoordinateTransform", FakeTransform)
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsProject", FakeProject)
    output_crs = FakeCrs("EPSG:3857")
    lines = FakeSource(
        [FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(1, 0)]))],
        crs=FakeCrs("EPSG:25830"),
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.CRS: output_crs,
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
    )

    algorithm.processAlgorithm({}, FakeProcessingContext(), FakeFeedback())

    assert sinks[algorithm.OUTPUT_NODES].crs == output_crs
    assert sinks[algorithm.OUTPUT_LINES].crs == output_crs
    assert [feature.geometry_value.asPoint().x() for feature in sinks[algorithm.OUTPUT_NODES].features] == [10, 11]
    assert [feature.geometry_value.asPoint().y() for feature in sinks[algorithm.OUTPUT_NODES].features] == [20, 20]


def test_network_from_lines_uses_dem_elevations(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)
    lines = FakeSource(
        [FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(1, 2), FakePoint(3, 4)]))]
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines, algorithm.INPUT_DEM: FakeRaster()},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
        enums={algorithm.ELEVATION_SOURCE: 2},
    )

    feedback = FakeFeedback()
    algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)

    assert [feature.attributes_value[2] for feature in sinks[algorithm.OUTPUT_NODES].features] == [3, 7]
    assert "Node elevation source: DEM raster" in feedback.info
    assert "Node elevations added from DEM: 2" in feedback.info


def test_network_from_lines_rejects_missing_dem(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)
    lines = FakeSource(
        [FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(1, 2), FakePoint(3, 4)]))]
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
        enums={algorithm.ELEVATION_SOURCE: 2},
    )

    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)
    assert feedback.errors == [
        "ERROR: DEM raster layer is required for the selected elevation source"
    ]
    assert sinks == {}


def test_network_from_lines_rejects_invalid_dem_elevations(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)

    class InvalidProvider:
        def __init__(self, values):
            self.values = list(values)

        def sample(self, point, band):
            return self.values.pop(0)

    for value in [(None, False), (None, True), (float("nan"), True), (float("inf"), True)]:
        lines = FakeSource(
            [FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(1, 2), FakePoint(3, 4)]))]
        )
        sinks = bind_common_parameters(
            monkeypatch,
            algorithm,
            sources={
                algorithm.INPUT: lines,
                algorithm.INPUT_DEM: FakeRasterWithProvider(InvalidProvider([(3.0, True), value])),
            },
            fields={
                algorithm.TOLERANCE: 0.001,
                algorithm.MASK_NODE: "N$",
                algorithm.INITIAL_NODE: 1,
                algorithm.INCREMENT_NODE: 1,
                algorithm.MASK_LINK: "L$",
                algorithm.INITIAL_LINK: 1,
                algorithm.INCREMENT_LINK: 1,
            },
            enums={algorithm.ELEVATION_SOURCE: 2},
        )

        feedback = FakeFeedback()
        with pytest.raises(QgsProcessingException):
            algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)
        assert feedback.errors == [
            "ERROR: DEM raster does not provide a valid elevation for all network nodes"
        ]
        assert sinks == {}


def test_network_from_lines_uses_landxml_elevations(monkeypatch, tmp_path):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)

    class FakeTin:
        def from_landxml(self, path, surface_name):
            assert path.endswith("surface.xml")
            assert surface_name == "ground"

        def elevations(self, points):
            return [10 + index for index, _ in enumerate(points)]

    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.TIN", FakeTin)
    landxml = tmp_path / "surface.xml"
    landxml.write_text("<LandXML />", encoding="utf-8")
    lines = FakeSource(
        [FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(1, 2), FakePoint(3, 4)]))]
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        files={algorithm.INPUT_LANDXML: landxml},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
            algorithm.SURFACE_NAME: "ground",
        },
        enums={algorithm.ELEVATION_SOURCE: 3},
    )

    feedback = FakeFeedback()
    algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)

    assert [feature.attributes_value[2] for feature in sinks[algorithm.OUTPUT_NODES].features] == [10, 11]
    assert "Node elevation source: LandXML TIN" in feedback.info
    assert "LandXML surface used: ground" in feedback.info


def test_network_from_lines_rejects_missing_landxml(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)
    lines = FakeSource(
        [FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(1, 2), FakePoint(3, 4)]))]
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
        enums={algorithm.ELEVATION_SOURCE: 3},
    )

    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)
    assert feedback.errors == [
        "ERROR: LandXML file is required for the selected elevation source"
    ]
    assert sinks == {}


def test_network_from_lines_rejects_invalid_landxml_elevations(monkeypatch, tmp_path):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsPointXY", lambda x, y: FakePoint(x, y))
    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.QgsGeometry", FakeQgsGeometry)

    class FakeTin:
        surface_name = "ground"

        def from_landxml(self, path, surface_name):
            pass

        def elevations(self, points):
            return [10.0, None]

    monkeypatch.setattr("wnt.processes.wnt_network_from_lines.TIN", FakeTin)
    landxml = tmp_path / "surface.xml"
    landxml.write_text("<LandXML />", encoding="utf-8")
    lines = FakeSource(
        [FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(1, 2), FakePoint(3, 4)]))]
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        files={algorithm.INPUT_LANDXML: landxml},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
        enums={algorithm.ELEVATION_SOURCE: 3},
    )

    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, FakeProcessingContext(), feedback)
    assert feedback.errors == [
        "ERROR: LandXML TIN does not provide a valid elevation for all network nodes"
    ]
    assert sinks == {}


def test_network_from_lines_extracts_qgis_multiline_parts_with_z():
    multiline = QgsMultiLineString()
    multiline.addGeometry(QgsLineString([QgsPoint(0, 0, 10), QgsPoint(1, 0, 11)]))
    multiline.addGeometry(QgsLineString([QgsPoint(1, 0, 11), QgsPoint(2, 0, 12)]))

    parts = NetworkFromLinesAlgorithm._line_parts(QgsGeometry(multiline))

    assert len(parts) == 2
    assert parts[0][0].z() == 10
    assert parts[1][-1].z() == 12


def test_network_from_lines_rejects_conflicting_z_elevations(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    lines = FakeSource(
        [
            FakeFeature(
                {},
                FakeGeometry(0, 0, polyline=[FakePoint(0, 0, 10.0), FakePoint(1, 0, 11.0)]),
            ),
            FakeFeature(
                {},
                FakeGeometry(1, 0, polyline=[FakePoint(1, 0, 11.5), FakePoint(2, 0, 12.0)]),
            ),
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
        enums={algorithm.ELEVATION_SOURCE: 1},
    )

    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == [
        "ERROR: Line endpoint elevations merged into a node differ more than tolerance"
    ]


def test_network_from_lines_rejects_missing_line_z_elevations(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_network_from_lines")
    lines = FakeSource(
        [
            FakeFeature(
                {},
                FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(1, 0, 11.0)]),
            ),
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: lines},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
        enums={algorithm.ELEVATION_SOURCE: 1},
    )

    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == [
        "ERROR: Line endpoint Z elevation source requires every input line endpoint to have a valid Z value"
    ]


def test_network_from_lines_rejects_invalid_and_looped(monkeypatch):
    algorithm = NetworkFromLinesAlgorithm()
    invalid = FakeSource([FakeFeature({}, FakeGeometry(0, 0, polyline=[FakePoint(0, 0)]), fid=7)])
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: invalid},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Invalid LineString geometry (FID: 7)"]

    looped = FakeSource(
        [
            FakeFeature(
                {},
                FakeGeometry(0, 0, polyline=[FakePoint(0, 0), FakePoint(0.0001, 0)]),
                fid=8,
            )
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT: looped},
        fields={
            algorithm.TOLERANCE: 0.001,
            algorithm.MASK_NODE: "N$",
            algorithm.INITIAL_NODE: 1,
            algorithm.INCREMENT_NODE: 1,
            algorithm.MASK_LINK: "L$",
            algorithm.INITIAL_LINK: 1,
            algorithm.INCREMENT_LINK: 1,
        },
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Looped LineString detected (FID: 8)"]


class FakeEpanetLibrary:
    def __init__(self, error_at=None, link_status=1.0, run_time=0, node_id=b"N1", link_id=b"L1"):
        self.error_at = error_at
        self.link_status = link_status
        self.run_time = run_time
        self.node_id = node_id
        self.link_id = link_id
        self.calls = {}
        self.next_calls = 0
        self.next_quality_calls = 0

    def _err(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1
        if self.error_at == name:
            return 77
        if self.error_at == (name, self.calls[name]):
            return 77
        return 0

    def ENgetversion(self, out):
        err = self._err("ENgetversion")
        if err:
            return err
        out._obj.value = 20200
        return 0

    def ENgeterror(self, code, out, max_len):
        value = f"EPANET toolkit error {code}".encode()
        if hasattr(out, "_obj"):
            out._obj.value = value
        else:
            out.value = value
        return 0

    def ENopen(self, inp, rpt, out=None):
        return self._err("ENopen")

    def ENgetcount(self, code, out):
        err = self._err("ENgetcount")
        if err:
            return err
        out._obj.value = 1
        return 0

    def ENopenH(self):
        return self._err("ENopenH")

    def ENinitH(self, save):
        return self._err("ENinitH")

    def ENrunH(self, out):
        err = self._err("ENrunH")
        if err:
            return err
        out._obj.value = self.run_time + self.next_calls * 3600
        return 0

    def ENgetnodeid(self, index, out):
        err = self._err("ENgetnodeid")
        if err:
            return err
        if hasattr(out, "_obj"):
            out._obj.value = self.node_id
        else:
            out.value = self.node_id
        return 0

    def ENgetnodevalue(self, index, parameter, out):
        err = self._err("ENgetnodevalue")
        if err:
            return err
        out._obj.value = float(parameter)
        return 0

    def ENgetlinkid(self, index, out):
        err = self._err("ENgetlinkid")
        if err:
            return err
        if hasattr(out, "_obj"):
            out._obj.value = self.link_id
        else:
            out.value = self.link_id
        return 0

    def ENgetlinkvalue(self, index, parameter, out):
        err = self._err("ENgetlinkvalue")
        if err:
            return err
        out._obj.value = self.link_status if parameter == 11 else float(parameter)
        return 0

    def ENnextH(self, out):
        err = self._err("ENnextH")
        if err:
            return err
        self.next_calls += 1
        out._obj.value = 0
        return 0

    def ENcloseH(self):
        return self._err("ENcloseH")

    def ENsolveH(self):
        return self._err("ENsolveH")

    def ENopenQ(self):
        return self._err("ENopenQ")

    def ENinitQ(self, save):
        return self._err("ENinitQ")

    def ENrunQ(self, out):
        err = self._err("ENrunQ")
        if err:
            return err
        out._obj.value = self.next_quality_calls * 3600
        return 0

    def ENnextQ(self, out):
        err = self._err("ENnextQ")
        if err:
            return err
        self.next_quality_calls += 1
        out._obj.value = 0
        return 0

    def ENcloseQ(self):
        return self._err("ENcloseQ")

    def ENclose(self):
        return self._err("ENclose")


class FakeToolkitConfig:
    def __init__(self, has_lib=True):
        self.has_lib = has_lib

    def read(self, path):
        return []

    def __getitem__(self, key):
        if not self.has_lib:
            raise KeyError(key)
        return {"lib": "fake-epanet"}


def patch_results_algorithm(monkeypatch, library=None, has_lib=True):
    patch_lightweight_qgis_feature_classes(monkeypatch, "wnt.processes.wnt_results_from_epanet")
    if has_lib:
        monkeypatch.setattr(
            "wnt.processes.wnt_results_from_epanet.EpanetToolkit.from_config",
            lambda: EpanetToolkit(library or FakeEpanetLibrary(), "fake-epanet"),
        )
    else:
        monkeypatch.setattr(
            "wnt.processes.wnt_results_from_epanet.EpanetToolkit.from_config",
            lambda: (_ for _ in ()).throw(
                EpanetConfigurationError("Configure EPANET toolkit library")
            ),
        )


def test_results_from_epanet_loads_node_and_link_results(monkeypatch, tmp_path):
    algorithm = ResultsFromEpanetAlgorithm()
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="utf-8")
    library = FakeEpanetLibrary()
    patch_results_algorithm(monkeypatch, library)
    sinks = bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: inp})

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    node_attrs = sinks[algorithm.OUTPUT_NODES].features[0].attributes_value
    link_attrs = sinks[algorithm.OUTPUT_LINES].features[0].attributes_value
    node_attrs[1] = node_attrs[1].rstrip("\x00")
    link_attrs[1] = link_attrs[1].rstrip("\x00")
    assert node_attrs == [
        "00:00:00",
        "N1",
        9.0,
        10.0,
        11.0,
    ]
    assert link_attrs == [
        "00:00:00",
        "L1",
        8.0,
        9.0,
        10.0,
        "OPEN",
        12.0,
        13.0,
    ]
    assert library.calls["ENcloseH"] == 1
    assert library.calls["ENclose"] == 1


def test_epanet_results_preserve_elapsed_hours_and_latin1_ids(monkeypatch, tmp_path):
    algorithm = ResultsFromEpanetAlgorithm()
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="latin-1")
    library = FakeEpanetLibrary(run_time=25 * 3600, node_id=b"N\xf3", link_id=b"L\xe1")
    patch_results_algorithm(monkeypatch, library)
    sinks = bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: inp})

    algorithm.processAlgorithm({}, FakeProcessingContext(), FakeFeedback())

    assert sinks[algorithm.OUTPUT_NODES].features[0].attributes_value[:2] == ["25:00:00", "Nó"]
    assert sinks[algorithm.OUTPUT_LINES].features[0].attributes_value[:2] == ["25:00:00", "Lá"]
    assert format_elapsed_time(49 * 3600 + 61) == "49:01:01"


def test_epanet_toolkit_rejects_missing_library_path(tmp_path):
    missing = tmp_path / "missing-epanet.dll"
    with pytest.raises(EpanetConfigurationError, match="EPANET toolkit library not found"):
        EpanetToolkit.from_library_path(missing)


def test_epanet_constants_are_resolved_by_toolkit_version():
    assert constants_for_version(20012).max_label_len == 15
    assert constants_for_version(20200).max_label_len == 31
    assert constants_for_version(20200).node_count == 0
    assert constants_for_version(20200).energy == 13


def test_results_from_epanet_loads_posix_library_and_closed_status(monkeypatch, tmp_path):
    algorithm = ResultsFromEpanetAlgorithm()
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="utf-8")

    patch_results_algorithm(monkeypatch, FakeEpanetLibrary(link_status=0.0))
    sinks = bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: inp})

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    assert sinks[algorithm.OUTPUT_LINES].features[0].attributes_value[5] == "CLOSED"


def test_results_from_epanet_loads_quality_results(monkeypatch, tmp_path):
    algorithm = ResultsFromEpanetAlgorithm()
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="utf-8")

    library = FakeEpanetLibrary()
    patch_results_algorithm(monkeypatch, library)
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        files={algorithm.INPUT: inp},
        enums={algorithm.RESULT_TYPE: algorithm.RESULT_QUALITY},
    )

    context = FakeProcessingContext()
    result = algorithm.processAlgorithm({}, context, FakeFeedback())

    assert result == {
        algorithm.OUTPUT_NODE_QUALITY: f"{algorithm.OUTPUT_NODE_QUALITY}_id",
        algorithm.OUTPUT_LINK_QUALITY: f"{algorithm.OUTPUT_LINK_QUALITY}_id",
    }
    node_attrs = sinks[algorithm.OUTPUT_NODE_QUALITY].features[0].attributes_value
    link_attrs = sinks[algorithm.OUTPUT_LINK_QUALITY].features[0].attributes_value
    node_attrs[1] = node_attrs[1].rstrip("\x00")
    link_attrs[1] = link_attrs[1].rstrip("\x00")
    assert node_attrs == ["00:00:00", "N1", 12.0]
    assert link_attrs == ["00:00:00", "L1", 14.0]
    assert library.calls["ENcloseQ"] == 1
    assert library.calls["ENclose"] == 1


def test_epanet_toolkit_closes_subsystems_when_results_fail(tmp_path):
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="utf-8")

    hydraulic_library = FakeEpanetLibrary(error_at="ENgetnodeid")
    with pytest.raises(EpanetError):
        EpanetToolkit(hydraulic_library, "fake-epanet").read_hydraulic_results(inp)
    assert hydraulic_library.calls["ENcloseH"] == 1
    assert hydraulic_library.calls["ENclose"] == 1

    quality_library = FakeEpanetLibrary(error_at="ENgetnodeid")
    with pytest.raises(EpanetError):
        EpanetToolkit(quality_library, "fake-epanet").read_quality_results(inp)
    assert quality_library.calls["ENcloseQ"] == 1
    assert quality_library.calls["ENclose"] == 1


def test_results_from_epanet_reports_configuration_and_toolkit_errors(monkeypatch, tmp_path):
    algorithm = ResultsFromEpanetAlgorithm()
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="utf-8")
    patch_results_algorithm(monkeypatch, has_lib=False)
    bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: inp})
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Configure EPANET toolkit library"]

    patch_results_algorithm(monkeypatch, FakeEpanetLibrary(error_at="ENopen"))
    bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: inp})
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: EPANET toolkit error 77"]


@pytest.mark.parametrize(
    "error_at",
    [
        "ENgetcount",
        ("ENgetcount", 2),
        "ENopenH",
        "ENinitH",
        "ENgetnodeid",
        "ENgetnodevalue",
        "ENgetlinkid",
        ("ENgetlinkvalue", 1),
        ("ENgetlinkvalue", 4),
        ("ENgetlinkvalue", 5),
        "ENnextH",
        "ENclose",
    ],
)
def test_results_from_epanet_reports_toolkit_errors_at_each_step(monkeypatch, tmp_path, error_at):
    algorithm = ResultsFromEpanetAlgorithm()
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="utf-8")
    patch_results_algorithm(monkeypatch, FakeEpanetLibrary(error_at=error_at))
    bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: inp})
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: EPANET toolkit error 77"]


def test_results_from_epanet_returns_empty_when_canceled(monkeypatch, tmp_path):
    algorithm = ResultsFromEpanetAlgorithm()
    inp = tmp_path / "model.inp"
    inp.write_text("[END]\n", encoding="utf-8")
    patch_results_algorithm(monkeypatch)
    bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: inp})

    assert algorithm.processAlgorithm({}, None, FakeFeedback(canceled=True)) == {}


def test_config_toolkit_writes_ini(monkeypatch, tmp_path):
    algorithm = ConfigToolkitAlgorithm()
    ini = tmp_path / "toolkit.ini"

    class FakeConfiguredToolkit:
        def check_available(self):
            return True

        def info(self):
            return ToolkitInfo(
                library_path=str(tmp_path / "epanet.dll"),
                platform="Windows",
                architecture="AMD64",
                version="2.2.0",
                api="legacy",
            )

    monkeypatch.setattr("wnt.processes.wnt_config_toolkit.toolkit_config_path", lambda: ini)
    monkeypatch.setattr(
        "wnt.processes.wnt_config_toolkit.EpanetToolkit.from_library_path",
        lambda lib_file: FakeConfiguredToolkit(),
    )
    bind_common_parameters(monkeypatch, algorithm, files={algorithm.INPUT: tmp_path / "epanet.dll"})

    feedback = FakeFeedback()
    result = algorithm.processAlgorithm({}, None, feedback)
    assert result == {algorithm.OUTPUT: str(ini)}
    assert "epanet.dll" in ini.read_text(encoding="utf-8")
    assert "Platform: Windows AMD64" in feedback.info
    assert "EPANET toolkit version: 2.2.0" in feedback.info


def test_validate_reports_all_problem_types(monkeypatch):
    algorithm = ValidateAlgorithm()
    nodes = FakeSource(
        [
            FakeFeature({"id": "N1"}),
            FakeFeature({"id": "N1"}),
            FakeFeature({"id": "ORPHAN"}),
        ],
        fields=fake_fields("id"),
    )
    links = FakeSource(
        [
            FakeFeature({"id": "L1", "start": "N1", "end": "MISSING"}),
            FakeFeature({"id": "L1", "start": "N1", "end": "N1"}),
        ],
        fields=fake_fields("id", "start", "end"),
    )
    sinks = bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
    )

    feedback = FakeFeedback()
    result = algorithm.processAlgorithm({}, None, feedback)

    assert result == {
        algorithm.OUTPUT_NODES: f"{algorithm.OUTPUT_NODES}_id",
        algorithm.OUTPUT_LINES: f"{algorithm.OUTPUT_LINES}_id",
    }
    node_messages = [feature.attributes()[-1] for feature in sinks[algorithm.OUTPUT_NODES].features]
    link_messages = [feature.attributes()[-1] for feature in sinks[algorithm.OUTPUT_LINES].features]
    assert "Duplicated." in node_messages[0]
    assert "Orphan." in node_messages[2]
    assert "Undefined node links." in link_messages[0]
    assert "Duplicate link. Loop." in link_messages[1]
    assert any("problems detected" in line for line in feedback.info)


def test_network_to_pipesizing_writes_pro_with_external_catalog(monkeypatch, tmp_path):
    algorithm = NetworkToPipesizingAlgorithm()
    output = tmp_path / "sizing.pro"
    epanet_file = tmp_path / "model.inp"
    input_catalog = tmp_path / "template.cat"
    epanet_file.write_text("[END]\n", encoding="utf-8")
    input_catalog.write_text("S1    100.0    120.0\n", encoding="utf-8")
    nodes = FakeSource(
        [FakeFeature({"id": "N1", "peak": 20, "fire": 10}), FakeFeature({"id": "N2", "peak": "", "fire": ""})],
        fields=fake_fields("id", "peak", "fire"),
    )
    links = FakeSource(
        [FakeFeature({"id": "L1", "group": "S1"}), FakeFeature({"id": "L2", "group": ""})],
        fields=fake_fields("id", "group"),
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        fields={
            algorithm.FIELD_PRESSURE: "peak",
            algorithm.FIELD_PRESSURE_FIRE: "fire",
            algorithm.FIELD_SERIES: "group",
            algorithm.PEAK_FACTOR: 1.5,
            algorithm.FIRE_FACTOR: 0.75,
            algorithm.FIRE_FLOW: 0.0,
        },
        files={algorithm.INPUT_EPANET: epanet_file, algorithm.INPUT_CATALOG: input_catalog, algorithm.OUTPUT: output},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    text = output.read_text(encoding="utf-8")
    output_catalog = output.with_suffix(".cat")
    assert "[SETTINGS]" in text
    assert "model.inp" in text
    assert "peak_factor 1.5" in text
    assert "fire_factor 0.75" in text
    assert "sizing.cat" in text
    assert "[PRESSURES]" in text
    assert "N1    20    10" in text
    assert "[FIRE_SCENARIOS]" in text
    assert "[PIPES]" in text
    assert "L1    S1" in text
    assert "[SERIES]" not in text
    assert output_catalog.read_text(encoding="utf-8") == "S1    100.0    120.0\n"
    output_catalog.write_text("old catalog", encoding="utf-8")
    feedback = FakeFeedback()
    algorithm.processAlgorithm({}, None, feedback)
    assert any("Existing pipe catalog will be overwritten" in line for line in feedback.info)

    unknown_links = FakeSource(
        [FakeFeature({"id": "L1", "group": "UNKNOWN"})],
        fields=fake_fields("id", "group"),
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: unknown_links},
        fields={
            algorithm.FIELD_PRESSURE: "peak",
            algorithm.FIELD_PRESSURE_FIRE: "fire",
            algorithm.FIELD_SERIES: "group",
            algorithm.PEAK_FACTOR: 1.0,
            algorithm.FIRE_FACTOR: 1.0,
            algorithm.FIRE_FLOW: 0.0,
        },
        files={algorithm.INPUT_EPANET: epanet_file, algorithm.INPUT_CATALOG: input_catalog, algorithm.OUTPUT: output},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Pipes reference unknown series: UNKNOWN"]

def test_network_to_ppno_writes_ext_from_catalog_and_rejects_crs(monkeypatch, tmp_path):
    algorithm = NetworkToPpnoAlgorithm()
    output = tmp_path / "output.ext"
    INPUT_EPANET = tmp_path / "model.inp"
    input_catalog = tmp_path / "template.cat"
    input_catalog.write_text("S1    100.0    0.1    10.0\n", encoding="latin-1")
    nodes = FakeSource([FakeFeature({"id": "N1", "pressure": 20}), FakeFeature({"id": "N2", "pressure": 0})])
    links = FakeSource([FakeFeature({"id": "L1", "group": "S1"}), FakeFeature({"id": "L2", "group": ""})])
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        fields={algorithm.FIELD_PRESSURE: "pressure", algorithm.FIELD_SERIES: "group"},
        files={algorithm.INPUT_EPANET: INPUT_EPANET, algorithm.INPUT_CATALOG: input_catalog, algorithm.OUTPUT: output},
        enums={algorithm.INPUT_ALGORITHMS: [0, 2]},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    text = output.read_text(encoding="latin-1")
    output_catalog = output.with_suffix(".cat")
    assert "[PIPE_CATALOG]" in text
    assert "output.cat" in text
    assert "Algorithm    DE    NSGA2" in text
    assert "N1    20" in text
    assert "L1    S1" in text
    assert output_catalog.read_text(encoding="latin-1") == "S1    100.0    0.1    10.0\n"
    output_catalog.write_text("old catalog", encoding="latin-1")
    feedback = FakeFeedback()
    algorithm.processAlgorithm({}, None, feedback)
    assert any("Existing pipe catalog will be overwritten" in line for line in feedback.info)

    bad_links = FakeSource([], crs=FakeCrs("EPSG:4326"))
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: bad_links},
        fields={algorithm.FIELD_PRESSURE: "pressure", algorithm.FIELD_SERIES: "group"},
        files={algorithm.INPUT_EPANET: INPUT_EPANET, algorithm.INPUT_CATALOG: input_catalog, algorithm.OUTPUT: output},
        enums={algorithm.INPUT_ALGORITHMS: [0, 2]},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Layers have different CRS"]

    catalog_with_header = tmp_path / "bad.cat"
    catalog_with_header.write_text("[PIPE_CATALOG]\nS1 100 120 10\n", encoding="latin-1")
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes, algorithm.INPUT_LINES: links},
        fields={algorithm.FIELD_PRESSURE: "pressure", algorithm.FIELD_SERIES: "group"},
        files={algorithm.INPUT_EPANET: INPUT_EPANET, algorithm.INPUT_CATALOG: catalog_with_header, algorithm.OUTPUT: output},
        enums={algorithm.INPUT_ALGORITHMS: [0, 2]},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: PPNO pipe catalog must not contain section headers"]


def test_scenario_exporters_validate_required_fields(monkeypatch, tmp_path):
    demand = DemandToEpanetScenarioAlgorithm()
    output = tmp_path / "demands.scn"
    nodes = FakeSource([FakeFeature({"id": "J1", "base": 1.0})], fields=FakeFields([FakeNamedField("id"), FakeNamedField("base")]))
    bind_common_parameters(
        monkeypatch,
        demand,
        sources={demand.INPUT_NODES: nodes},
        fields={demand.FIELD_DEMAND: ["base"]},
        files={demand.OUTPUT: output},
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        demand.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Node layer is missing required fields: type"]

    pipe = PipePropertiesToEpanetScenarioAlgorithm()
    links = FakeSource([FakeFeature({"id": "P1", "type": "PIPE", "diameter": 100})])
    bind_common_parameters(
        monkeypatch,
        pipe,
        sources={pipe.INPUT_LINES: links},
        fields={pipe.FIELD_DIAMETER: "diameter", pipe.FIELD_ROUGHNESS: "roughness"},
        files={pipe.OUTPUT: output},
    )
    feedback = FakeFeedback()
    with pytest.raises(QgsProcessingException):
        pipe.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Link layer is missing required fields: roughness"]


def test_demand_to_epanet_scenario_writes_selected_junction_demands(monkeypatch, tmp_path):
    algorithm = DemandToEpanetScenarioAlgorithm()
    output = tmp_path / "demands.scn"
    nodes = FakeSource(
        [
            FakeFeature({"id": "J1", "type": "JUNCTION", "base": 1.2, "fire": 0}),
            FakeFeature({"id": "R1", "type": "RESERVOIR", "base": 9.9, "fire": 1}),
            FakeFeature({"id": "Jó", "type": "JUNCTION", "base": 2.5, "fire": 3.5}),
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes},
        fields={algorithm.FIELD_DEMAND: ["base", "fire"]},
        files={algorithm.OUTPUT: output},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    text = output.read_text(encoding="latin-1")
    assert "J1  1.2  base" in text
    assert "Jó  2.5  base" in text
    assert "Jó  3.5  fire" in text
    assert b"J\xf3" in output.read_bytes()
    assert "R1" not in text

    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_NODES: nodes},
        fields={algorithm.FIELD_DEMAND: []},
        files={algorithm.OUTPUT: output},
    )
    feedback = FakeFeedback()

    with pytest.raises(QgsProcessingException):

        algorithm.processAlgorithm({}, None, feedback)
    assert feedback.errors == ["ERROR: Field containing demand is required"]


def test_pipe_properties_to_epanet_scenario_writes_only_pipes(monkeypatch, tmp_path):
    algorithm = PipePropertiesToEpanetScenarioAlgorithm()
    output = tmp_path / "scenario.scn"
    links = FakeSource(
        [
            FakeFeature({"id": "P1", "type": "PIPE", "diameter": 100, "roughness": 120}),
            FakeFeature({"id": "V1", "type": "PRV", "diameter": 50, "roughness": 80}),
            FakeFeature({"id": "P2", "type": "CVPIPE", "diameter": 150, "roughness": 130}),
        ]
    )
    bind_common_parameters(
        monkeypatch,
        algorithm,
        sources={algorithm.INPUT_LINES: links},
        fields={algorithm.FIELD_DIAMETER: "diameter", algorithm.FIELD_ROUGHNESS: "roughness"},
        files={algorithm.OUTPUT: output},
    )

    result = algorithm.processAlgorithm({}, None, FakeFeedback())

    assert result == {algorithm.OUTPUT: str(output)}
    text = output.read_text(encoding="latin-1")
    assert "P1    100" in text
    assert "P2    150" in text
    assert "V1" not in text
