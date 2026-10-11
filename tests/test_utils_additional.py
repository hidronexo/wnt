"""Additional coverage for pure utility modules."""

import builtins
import textwrap

import pytest

from wnt.utils.utils_core import (
    WntFormatError,
    WntGeometryError,
    WntLink,
    WntNetwork,
    WntNode,
    format_id,
    net_from_linestrings,
    polyline_length,
    xy,
)
from wnt.utils.utils_graph import (
    Graph,
    graph_from_records,
    node_degrees_from_records,
    validate_records,
)
from wnt.utils.utils_landxml import network_from_xml
from wnt.utils import safe_xml
from wnt.utils.safe_xml import _stdlib_parse


def tin_helpers():
    pytest.importorskip("qgis")
    from wnt.utils.utils_tin import TIN, Triangle, surface_names

    return TIN, Triangle, surface_names


def test_xy_accepts_indexed_and_qgis_like_points():
    """Coordinate helpers work with tuples and objects exposing x/y methods."""

    class Point:
        def x(self):
            return 3

        def y(self):
            return 4

    assert xy((1, 2, 9)) == (1, 2)
    assert xy(Point()) == (3, 4)


def test_polyline_length_rejects_bad_geometry():
    with pytest.raises(ValueError, match="Bad geometry"):
        polyline_length([(0, 0), object()])


def test_format_id_masks_and_plain_prefixes():
    assert format_id(7, "N-$$") == "N-07"
    assert format_id(7, "NODE") == "NODE7"


def test_net_from_linestrings_error_and_union_branches():
    with pytest.raises(Exception, match="Zero length"):
        net_from_linestrings([[(0, 0), (0, 0)]], 0)
    with pytest.raises(Exception, match="Looped"):
        net_from_linestrings([[(0, 0), (0.001, 0)]], 0.01)
    with pytest.raises(Exception, match="Looped"):
        net_from_linestrings([[(0, 0), (0.01, 0)]], 0.01)

    nodes, links = net_from_linestrings(
        [
            [(0, 0), (1, 0)],
            [(1.01, 0), (2, 0)],
            [(2.01, 0), (3, 0)],
        ],
        0.02,
    )

    assert len(nodes) == 4
    assert links[0][1] == links[1][0]
    assert links[1][1] == links[2][0]


def test_node_validation_and_wkt_parsing():
    node = WntNode("J1")

    assert node.name() == "J1"
    node.from_wkt('Point Z (1 2 3)')
    node.from_wkt('Point M (1 2 99)')
    node.from_wkt('Point ZM (1 2 3 99)')
    node.set_elevation("12.5")
    node.set_type("junction")

    assert node.get_geometry() == (1.0, 2.0)
    assert node.get_elevation() == 12.5
    assert node.get_type() == "JUNCTION"

    with pytest.raises(Exception, match="Bad geometry"):
        node.set_geometry(("x", 2))
    with pytest.raises(Exception, match="Bad elevation"):
        node.set_elevation("high")
    with pytest.raises(Exception, match="Incorrect type"):
        node.set_type("unknown")
    with pytest.raises(Exception, match="Incorrect type"):
        node.set_type(None)
    with pytest.raises(WntFormatError, match="Incorrect WKT"):
        node.from_wkt("not a point")


def test_link_validation_wkt_and_accessors():
    link = WntLink("P1", "J1", "J2")

    assert link.name() == "P1"
    assert link.start() == "J1"
    assert link.end() == "J2"
    link.from_wkt('LineString Z (0 0 0, 1 0 0, 1 1 0)')
    link.from_wkt('LineString M (0 0 7, 1 0 8, 1 1 9)')
    link.from_wkt('LineString ZM (0 0 1 7, 1 0 2 8, 1 1 3 9)')
    link.set_type("pipe")

    assert link.get_geometry()[0] == (0.0, 0.0)
    assert link.get_geometry()[-1] == (1.0, 1.0)
    assert link.get_vertices() == [(1.0, 0.0)]
    assert link.to_wkt() == "LINESTRING (0.0 0.0, 1.0 0.0, 1.0 1.0)"
    assert polyline_length(link.get_geometry()) == pytest.approx(2.0)
    assert link.get_type() == "PIPE"

    with pytest.raises(WntGeometryError, match="at least 2 points"):
        link.set_geometry([(0, 0)])
    with pytest.raises(Exception, match="Looped"):
        link.set_geometry([(0, 0), (0, 0)])
    with pytest.raises(Exception, match="Bad geometry"):
        link.set_geometry([(0, 0), ("bad", 1)])
    with pytest.raises(Exception, match="Bad type"):
        link.set_type("bad")
    with pytest.raises(Exception, match="Bad type"):
        link.set_type(None)
    with pytest.raises(WntFormatError, match="Multi-geometry"):
        link.from_wkt("MultiLineString((0 0, 1 1))")
    with pytest.raises(Exception, match="Incorrect WKT"):
        link.from_wkt(None)
    with pytest.raises(Exception, match="Incorrect WKT"):
        link.from_wkt("LineString(bad)")


def test_network_validation_and_exports(tmp_path):
    network = WntNetwork()
    j1 = WntNode("J1")
    j1.set_type("JUNCTION")
    j1.set_elevation(0)
    j1.set_geometry((0, 0))
    j2 = WntNode("J2")
    j2.set_type("RESERVOIR")
    j2.set_elevation(10)
    j2.set_geometry((1, 0))
    j3 = WntNode("J3")
    j3.set_type("TANK")
    j3.set_geometry((2, 0))
    duplicate = WntNode("J2")
    duplicate.set_geometry((3, 0))
    network.add_node(j1)
    network.add_node(j2)
    network.add_node(j3)
    with pytest.raises(ValueError, match="Duplicated node id: J2"):
        network.add_node(duplicate)

    pipe = WntLink("P1", "J1", "J2")
    pipe.set_type("CVPIPE")
    pipe.epanet["length"] = 1.25
    pipe.set_geometry([(0, 0), (0.5, 0.2), (1, 0)])
    pump = WntLink("PU1", "J2", "J3")
    pump.set_type("PUMP")
    pump.set_geometry([(1, 0), (2, 0)])
    valve = WntLink("V1", "J3", "J3")
    valve.set_type("PRV")
    valve.set_geometry([(2, 0), (2, 1)])
    duplicate_link = WntLink("P1", "J3", "MISSING")
    duplicate_link.set_geometry([(2, 0), (3, 0)])
    network.add_link(pipe)
    network.add_link(pump)
    network.add_link(valve)
    with pytest.raises(ValueError, match="Duplicated link id: P1"):
        network.add_link(duplicate_link)

    assert network.nodes()[0] is j1
    assert network.links()[0] is pipe
    with pytest.raises(Exception, match="Bad type"):
        network.add_node(object())
    with pytest.raises(Exception, match="Must be Link"):
        network.add_link(object())

    template = tmp_path / "template.inp"
    output = tmp_path / "output.inp"
    template.write_text(
        textwrap.dedent(
            """
            [TITLE]
            [JUNCTIONS]
            [RESERVOIRS]
            [TANKS]
            [PIPES]
            [PUMPS]
            [VALVES]
            [COORDINATES]
            [VERTICES]
            [BACKDROP]
            DIMENSIONS 0 0 0 0
            [END]
            """
        ).strip(),
        encoding="latin-1",
    )

    network.to_epanet(output, template)

    text = output.read_text(encoding="latin-1")
    assert "P1    J1    J2    1.25" in text
    assert "PU1    J2    J3" in text
    assert "V1    J3    J3" in text
    assert "DIMENSIONS" in text


def test_graph_module_record_helpers(tmp_path):
    node_ids = ["N1", "N2", "ORPHAN", "N1"]
    links = [("L1", "N1", "N2"), ("L1", "N2", "MISSING"), ("LOOP", "N1", "N1")]

    assert node_degrees_from_records(node_ids, links) == {
        "N1": 3,
        "N2": 2,
        "ORPHAN": 0,
        "MISSING": 1,
    }
    assert validate_records(node_ids, links) == {
        "orphan nodes": {"ORPHAN"},
        "duplicate nodes": {"N1"},
        "undefined node links": {"L1"},
        "duplicate links": {"L1"},
        "loops": {"LOOP"},
    }
    assert validate_records(
        ["J1"], [("P1", "MISSING", "J1")]
    )["undefined node links"] == {"P1"}

    tgf = tmp_path / "network.tgf"
    with pytest.raises(ValueError, match="undefined nodes: L1"):
        graph_from_records(node_ids, links, tgf)
    assert not tgf.exists()

    graph_from_records(["N1", "N2"], [("L1", "N1", "N2")], tgf)
    assert tgf.read_text(encoding="utf-8").splitlines() == [
        "0 N1 ",
        "1 N2 ",
        "# ",
        "0 1 L1 ",
    ]


def test_epanet_import_covers_all_supported_sections(tmp_path):
    inp = tmp_path / "full.inp"
    inp.write_text(
        textwrap.dedent(
            """
            [JUNCTIONS]
            J1 0
            J2 5
            [RESERVOIRS]
            R1 10
            [TANKS]
            T1 7
            [COORDINATES]
            J1 0 0
            J2 1 0
            R1 2 0
            T1 3 0
            UNKNOWN 9 9
            [PIPES]
            P1 J1 J2 1.0 100 120 0 CV
            P2 J2 R1 1.0 100 120 0 Open
            [PUMPS]
            PU1 R1 T1 HEAD 1
            [VALVES]
            V1 T1 J1 100 PRV 0 0
            [VERTICES]
            P1 0.5 0.5
            UNKNOWN 8 8
            [END]
            """
        ).strip(),
        encoding="latin-1",
    )

    network = WntNetwork()
    network.from_epanet(inp)

    assert [node.get_type() for node in network.nodes()] == [
        "JUNCTION",
        "JUNCTION",
        "RESERVOIR",
        "TANK",
    ]
    assert [link.get_type() for link in network.links()] == ["CVPIPE", "PIPE", "PUMP", "PRV"]
    assert network.links()[0].get_vertices() == [(0.5, 0.5)]


def test_epanet_import_parses_optional_pipe_status_and_validates_columns(tmp_path):
    inp = tmp_path / "pipes.inp"
    inp.write_text(
        "[PIPES]\nP1 N1 N2 10 100 120 CV\nP2 N2 N3 20 150 130 0.5 CLOSED\n[END]\n",
        encoding="latin-1",
    )

    network = WntNetwork()
    network.from_epanet(inp)

    first, second = network.links()
    assert first.get_type() == "CVPIPE"
    assert first.epanet["minor_loss"] is None
    assert first.epanet["status"] == "CV"
    assert second.epanet["minor_loss"] == "0.5"
    assert second.epanet["status"] == "CLOSED"

    inp.write_text("[PIPES]\nBROKEN N1 N2 10 100\n[END]\n", encoding="latin-1")
    with pytest.raises(ValueError, match="Invalid EPANET pipe definition"):
        WntNetwork().from_epanet(inp)


@pytest.mark.parametrize(
    "text, message",
    [
        ("[COORDINATES]\nBROKEN 1\n[END]\n", "Invalid EPANET coordinate definition"),
        ("[VALVES]\nV1 N1 N2 100\n[END]\n", "Invalid EPANET valve definition"),
        ("[VERTICES]\nP1 0\n[END]\n", "Invalid EPANET vertex definition"),
    ],
)
def test_epanet_import_validates_truncated_coordinate_valve_and_vertex(tmp_path, text, message):
    inp = tmp_path / "truncated.inp"
    inp.write_text(text, encoding="latin-1")

    with pytest.raises(ValueError, match=message):
        WntNetwork().from_epanet(inp)


def test_epanet_import_ignores_extra_coordinate_and_vertex_tokens(tmp_path):
    inp = tmp_path / "extra_tokens.inp"
    inp.write_text(
        textwrap.dedent(
            """
            [JUNCTIONS]
            J1 0
            J2 0
            [COORDINATES]
            J1 0 0 ignored
            J2 1 0 ignored
            [PIPES]
            P1 J1 J2 1 100 120
            [VERTICES]
            P1 0.5 0.25 ignored
            [END]
            """
        ).strip(),
        encoding="latin-1",
    )

    network = WntNetwork()
    network.from_epanet(inp)

    assert network.nodes()[0].get_geometry() == (0.0, 0.0)
    assert network.links()[0].get_vertices() == [(0.5, 0.25)]


def test_epanet_import_skips_link_geometry_when_nodes_are_missing(tmp_path):
    inp = tmp_path / "missing_nodes.inp"
    inp.write_text(
        textwrap.dedent(
            """
            [JUNCTIONS]
            J1 0
            [COORDINATES]
            J1 0 0
            [PIPES]
            P1 J1 MISSING 1.0 100 120 0 Open
            [VERTICES]
            P1 0.5 0.5
            [END]
            """
        ).strip(),
        encoding="latin-1",
    )

    network = WntNetwork()
    network.from_epanet(inp)

    assert network.links()[0].get_geometry() is None


def test_epanet_export_elevation_truthy_branches(tmp_path):
    network = WntNetwork()
    for name, kind, elevation, x in [
        ("J1", "JUNCTION", 3, 0),
        ("R1", "RESERVOIR", 4, 1),
        ("T1", "TANK", 5, 2),
    ]:
        node = WntNode(name)
        node.set_type(kind)
        node.set_elevation(elevation)
        node.set_geometry((x, 0))
        network.add_node(node)

    link = WntLink("P1", "J1", "R1")
    link.set_geometry([(0, 0), (1, 0)])
    network.add_link(link)

    template = tmp_path / "template.inp"
    output = tmp_path / "output.inp"
    template.write_text(
        "[TITLE]\n[JUNCTIONS]\n[RESERVOIRS]\n[TANKS]\n[PIPES]\n[PUMPS]\n"
        "[VALVES]\n[COORDINATES]\n[VERTICES]\n[BACKDROP]\nKEEP\n[END]\n",
        encoding="latin-1",
    )

    network.to_epanet(output, template)
    text = output.read_text(encoding="latin-1")

    assert "J1    3.0    0.0" in text
    assert "R1    4.0" in text
    assert "T1    5.0" in text
    assert "KEEP" in text


def test_epanet_export_adds_missing_template_sections(tmp_path):
    network = WntNetwork()
    start = WntNode("J1")
    start.set_type("JUNCTION")
    start.set_geometry((0, 0))
    network.add_node(start)
    end = WntNode("J2")
    end.set_type("JUNCTION")
    end.set_geometry((2, 0))
    network.add_node(end)
    link = WntLink("P1", "J1", "J2")
    link.set_geometry([(0, 0), (1, 1), (2, 0)])
    network.add_link(link)

    template = tmp_path / "sparse.inp"
    output = tmp_path / "output.inp"
    template.write_text("[OPTIONS]\nUNITS LPS\n[END]\n", encoding="latin-1")

    network.to_epanet(output, template)
    text = output.read_text(encoding="latin-1")

    assert "[JUNCTIONS]" in text
    assert "[PIPES]" in text
    assert "[COORDINATES]" in text
    assert "[VERTICES]" in text
    assert "P1    1.0    1.0" in text
    assert "[BACKDROP]" in text
    assert "DIMENSIONS" in text
    assert "[TITLE]" in text


def test_epanet_export_without_coordinates_preserves_backdrop(tmp_path):
    network = WntNetwork()
    node = WntNode("J1")
    node.set_type("JUNCTION")
    network.add_node(node)

    template = tmp_path / "no_coordinates.inp"
    output = tmp_path / "output.inp"
    template.write_text(
        "[BACKDROP]\nDIMENSIONS 1 2 3 4\nKEEP\n[END]\n",
        encoding="latin-1",
    )

    network.to_epanet(output, template)
    text = output.read_text(encoding="latin-1")

    assert "J1    0.0    0.0" in text
    assert "[COORDINATES]" not in text
    assert "DIMENSIONS 1 2 3 4" in text
    assert "KEEP" in text
    assert "1000000000000" not in text


def test_epanet_export_reservoir_without_elevation(tmp_path):
    network = WntNetwork()
    reservoir = WntNode("R0")
    reservoir.set_type("RESERVOIR")
    reservoir.set_geometry((0, 0))
    network.add_node(reservoir)

    template = tmp_path / "template.inp"
    output = tmp_path / "output.inp"
    template.write_text(
        "[TITLE]\n[JUNCTIONS]\n[RESERVOIRS]\n[TANKS]\n[PIPES]\n[PUMPS]\n"
        "[VALVES]\n[COORDINATES]\n[VERTICES]\n[BACKDROP]\n[END]\n",
        encoding="latin-1",
    )

    network.to_epanet(output, template)

    assert "R0    0.0" in output.read_text(encoding="latin-1")



def test_graph_classifies_tree_and_mesh_edges():
    graph = Graph()
    graph.add_edge("T1", "A", "B")
    graph.add_edge("T2", "B", "C")
    graph.add_edge("M1", "D", "E")
    graph.add_edge("M2", "E", "F")
    graph.add_edge("M3", "F", "D")

    assert set(graph.get_nodes()) == {"A", "B", "C", "D", "E", "F"}
    assert graph.node_count() == 6
    assert graph.edge_count() == 5
    assert graph.get_incident_edges("B") == {"T1", "T2"}
    assert graph.get_contiguous_edges("T1") == {"T2"}
    assert graph.get_degrees()["B"] == 2
    assert graph.classify() == {
        "T1": ("BRANCHED", 1),
        "T2": ("BRANCHED", 1),
        "M1": ("MESHED", 1),
        "M2": ("MESHED", 1),
        "M3": ("MESHED", 1),
    }

    with pytest.raises(NameError, match="exists"):
        graph.add_edge("T1", "X", "Y")

    fresh = Graph()
    fresh.add_edge("M1", "A", "B")
    fresh.add_edge("M2", "B", "C")
    fresh.add_edge("M3", "C", "A")
    assert fresh.classify() == {
        "M1": ("MESHED", 1),
        "M2": ("MESHED", 1),
        "M3": ("MESHED", 1),
    }


def test_graph_classification_uses_linear_adjacency_and_stable_components(monkeypatch):
    graph = Graph()
    for label, start, end in [
        ("T1", "A", "B"),
        ("T2", "B", "C"),
        ("U1", "X", "Y"),
        ("M1", "D", "E"),
        ("M2", "E", "F"),
        ("M3", "F", "D"),
        ("N1", "G", "H"),
        ("N2", "H", "I"),
        ("N3", "I", "G"),
    ]:
        graph.add_edge(label, start, end)

    monkeypatch.setattr(
        graph, "get_incident_edges",
        lambda *_: (_ for _ in ()).throw(AssertionError("quadratic scan used")),
    )
    monkeypatch.setattr(
        graph, "get_contiguous_edges",
        lambda *_: (_ for _ in ()).throw(AssertionError("quadratic scan used")),
    )

    classified = graph.classify()

    assert classified["T1"] == ("BRANCHED", 1)
    assert classified["T2"] == ("BRANCHED", 1)
    assert classified["U1"] == ("BRANCHED", 2)
    assert {classified[label] for label in ("M1", "M2", "M3")} == {("MESHED", 1)}
    assert {classified[label] for label in ("N1", "N2", "N3")} == {("MESHED", 2)}


def test_tin_triangle_and_landxml_loading(tmp_path):
    TIN, Triangle, _surface_names = tin_helpers()
    triangle = Triangle((0, 0, 1), (1, 0, 2), (0, 1, 3))

    assert triangle.xy_area() == 0.5
    assert triangle.is_inside((0.25, 0.25))
    assert not triangle.is_inside((2, 2))
    assert triangle.z((0.25, 0.25)) == pytest.approx(1.75)

    xml = tmp_path / "surface.xml"
    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <Surfaces>
                <Surface name="Ground">
                  <Definition surfType="TIN">
                    <Pnts>
                      <P id="1">0 0 1</P>
                      <P id="2">0 1 2</P>
                      <P id="3">1 0 3</P>
                    </Pnts>
                    <Faces><F>1 2 3</F></Faces>
                  </Definition>
                  <Metadata />
                </Surface>
              </Surfaces>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    tin = TIN()
    tin.from_landxml(xml, "Ground")

    assert tin.elevations([(0.25, 0.25), (5, 5)]) == [pytest.approx(1.75), None]

    with pytest.raises(ValueError, match="Requested TIN surface was not found"):
        TIN().from_landxml(xml, "Missing")


def test_tin_reload_replaces_previous_surface(tmp_path):
    TIN, _Triangle, _surface_names = tin_helpers()
    xml = tmp_path / "surfaces.xml"
    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <Surfaces>
                <Surface name="Ground">
                  <Definition surfType="TIN">
                    <Pnts>
                      <P id="1">0 0 1</P>
                      <P id="2">0 1 2</P>
                      <P id="3">1 0 3</P>
                    </Pnts>
                    <Faces><F>1 2 3</F></Faces>
                  </Definition>
                </Surface>
                <Surface name="Roof">
                  <Definition surfType="TIN">
                    <Pnts>
                      <P id="1">0 0 10</P>
                      <P id="2">0 1 20</P>
                      <P id="3">1 0 30</P>
                    </Pnts>
                    <Faces><F>1 2 3</F></Faces>
                  </Definition>
                </Surface>
              </Surfaces>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    tin = TIN()
    tin.from_landxml(xml, "Ground")
    assert tin.elevations([(0.25, 0.25)]) == [pytest.approx(1.75)]

    tin.from_landxml(xml, "Roof")
    assert tin.elevations([(0.25, 0.25)]) == [pytest.approx(17.5)]


def test_tin_rejects_degenerate_faces(tmp_path):
    TIN, _Triangle, _surface_names = tin_helpers()
    xml = tmp_path / "surface.xml"
    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <Surfaces>
                <Surface name="FlatLine">
                  <Definition surfType="TIN">
                    <Pnts>
                      <P id="1">0 0 1</P>
                      <P id="2">1 1 2</P>
                      <P id="3">2 2 3</P>
                    </Pnts>
                    <Faces><F>1 2 3</F></Faces>
                  </Definition>
                </Surface>
              </Surfaces>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-zero XY area"):
        TIN().from_landxml(xml, "FlatLine")


def test_tin_spatial_index_limits_candidate_triangles(tmp_path):
    TIN, _Triangle, _surface_names = tin_helpers()
    xml = tmp_path / "surface.xml"
    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <Surfaces>
                <Surface name="Ground">
                  <Definition surfType="TIN">
                    <Pnts>
                      <P id="1">100 100 0</P>
                      <P id="2">100 101 0</P>
                      <P id="3">101 100 0</P>
                      <P id="4">0 0 10</P>
                      <P id="5">0 1 20</P>
                      <P id="6">1 0 30</P>
                    </Pnts>
                    <Faces>
                      <F>1 2 3</F>
                      <F>4 5 6</F>
                    </Faces>
                  </Definition>
                </Surface>
              </Surfaces>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    tin = TIN()
    tin.from_landxml(xml, "Ground")

    def fail_if_checked(point):
        raise AssertionError(f"Far triangle should not be checked for {point}")

    tin._triangles[0].is_inside = fail_if_checked

    assert tin.elevations([(0.25, 0.25)]) == [pytest.approx(17.5)]


def test_landxml_pipe_network_parser(tmp_path):
    xml = tmp_path / "network.xml"
    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <CoordinateSystem epsgCode="EPSG:25830" />
              <PipeNetworks>
                <PipeNetwork name="Storm" pipeNetType="storm">
                  <Struct name="S 1 (Storm)" desc="Inlet" elevSump="1" elevRim="3">
                    <Center>10 20</Center>
                    <Invert refPipe="P 1 (Storm)" elev="1.5" />
                  </Struct>
                  <Struct name="S2" desc="Outlet" elevSump="2" elevRim="5">
                    <Center>11 21</Center>
                    <Invert refPipe="P 1 (Storm)" elev="2.5" />
                  </Struct>
                  <Struct name="D1" desc="Dummy Null Structure for LandXML purposes" elevSump="0" elevRim="0" />
                  <Pipe name="P 1 (Storm)" refStart="S 1 (Storm)" refEnd="S2" length="12.3456" slope="0.012345">
                    <CircPipe diameter="300" />
                  </Pipe>
                </PipeNetwork>
              </PipeNetworks>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    data = network_from_xml(xml)
    storm = data["networks"]["Storm"]

    assert data["epsg_code"] == "EPSG:25830"
    assert data["node_fields"][:2] == ("origin", "net_type")
    assert data["link_fields"][:2] == ("origin", "net_type")
    assert storm["node_fields"] == (
        "origin",
        "net_type",
        "id",
        "type",
        "invert_elv",
        "rim_elv",
        "max_depth",
    )
    assert "diameter" not in storm["link_fields"]
    assert "status" not in storm["link_fields"]
    assert set(storm["nodes"]) == {"S_1", "S2"}
    assert set(storm["links"]) == {"P_1"}
    assert storm["nodes"]["S_1"]["id"] == "S_1"
    assert storm["nodes"]["S_1"]["x"] == 10
    assert storm["nodes"]["S_1"]["max_depth"] == 2
    assert storm["nodes"]["S_1"]["type"] == "manhole"
    assert storm["links"]["P_1"]["start"] == "S_1"
    assert storm["links"]["P_1"]["end"] == "S2"
    assert storm["links"]["P_1"]["length"] == 12.346
    assert storm["links"]["P_1"]["geom_shape"] == "circular"
    assert storm["links"]["P_1"]["geom_dim1"] == 0.3
    assert storm["links"]["P_1"]["inv_start"] == 1.5
    assert storm["links"]["P_1"]["start_os"] == 0.5
    assert storm["links"]["P_1"]["end_os"] == 0.5
    assert storm["links"]["P_1"]["slope"] == pytest.approx(-8.0998)

    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <CoordinateSystem ogcWktCode="LOCAL_CS[]" />
              <PipeNetwork name="Storm" pipeNetType="storm">
                <Struct name="S1" desc="Inlet" elevSump="1" elevRim="3">
                  <Center>10 20</Center>
                  <Invert refPipe="P1" elev="1.5" />
                </Struct>
                <Struct name="S2" desc="Outlet" elevSump="2" elevRim="5">
                  <Center>11 21</Center>
                  <Invert refPipe="P1" elev="2.5" />
                </Struct>
                <Pipe name="P1" refStart="S1" refEnd="S2" length="12" slope="0.01">
                  <RectPipe width="2" height="3" />
                </Pipe>
              </PipeNetwork>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    data = network_from_xml(xml)
    assert data["wkt_crs"] == "LOCAL_CS[]"
    assert data["networks"]["Storm"]["links"]["P1"]["geom_shape"] == "box"
    assert data["networks"]["Storm"]["links"]["P1"]["geom_dim1"] == 3.0
    assert data["networks"]["Storm"]["links"]["P1"]["geom_dim2"] == 2.0

    xml.write_text(
        """
        <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
          <CoordinateSystem ogcWktCode="LOCAL_CS[]" />
          <PipeNetwork name="Agua potable">
            <Struct name="N1" elevSump="1"><Center>0 0</Center></Struct>
            <Struct name="N2" elevSump="2"><Center>1 0</Center></Struct>
            <Pipe name="P1" refStart="N1" refEnd="N2" length="10">
              <CircPipe diameter="0.3" />
            </Pipe>
          </PipeNetwork>
        </LandXML>
        """,
        encoding="utf-8",
    )
    data = network_from_xml(xml)
    pressure = data["networks"]["Agua potable"]
    assert pressure["net_type"] == "water"
    assert pressure["node_fields"] == (
        "origin",
        "net_type",
        "id",
        "type",
        "elevation",
        "demand",
        "pattern",
        "init_lvl",
        "min_lvl",
        "max_lvl",
    )
    assert pressure["nodes"]["N1"]["type"] == "junction"
    assert pressure["nodes"]["N1"]["demand"] == 0.0
    assert pressure["links"]["P1"]["diameter"] == 300.0
    assert pressure["links"]["P1"]["status"] == "open"


def test_landxml_parser_handles_accents_missing_centers_and_duplicate_names(tmp_path):
    xml = tmp_path / "duplicate_networks.xml"
    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <PipeNetwork name="Agua" pipeNetType="water">
                <Struct name="Depósito 1"><Center>0 0</Center></Struct>
                <Struct name="N2"><Center>1 0</Center></Struct>
                <Struct name="NoCenter" />
                <Pipe name="Válvula 1" refStart="Depósito 1" refEnd="N2" length="1" />
                <Pipe name="Discarded" refStart="NoCenter" refEnd="N2" length="1" />
              </PipeNetwork>
              <PipeNetwork name="Agua" pipeNetType="water">
                <Struct name="N3"><Center>2 0</Center></Struct>
              </PipeNetwork>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    data = network_from_xml(xml)

    assert list(data["networks"]) == ["Agua", "Agua_2"]
    first = data["networks"]["Agua"]
    assert first["nodes"]["Depósito_1"]["type"] == "tank"
    assert "NoCenter" not in first["nodes"]
    assert first["links"]["Válvula_1"]["type"] == "valve"
    assert "Discarded" not in first["links"]
    assert data["networks"]["Agua_2"]["layer_base"] == "Agua_2"


def test_landxml_parser_handles_optional_crs_desc_and_inverts(tmp_path):
    xml = tmp_path / "network.xml"
    xml.write_text(
        textwrap.dedent(
            """
            <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
              <PipeNetwork name="Storm" pipeNetType="storm">
                <Struct name="S1" elevSump="1" elevRim="3">
                  <Center>10 20</Center>
                  <Invert refPipe="P1" elev="1.5" />
                </Struct>
                <Struct name="S2" elevSump="2" elevRim="5">
                  <Center>11 21</Center>
                  <Invert refPipe="P1" elev="2.5" />
                </Struct>
                <Struct name="S3" elevSump="2" elevRim="5">
                  <Center>12 22</Center>
                </Struct>
                <Pipe name="P1" refStart="S1" refEnd="S2" length="12">
                  <CircPipe diameter="300" />
                </Pipe>
                <Pipe name="P2" refStart="S2" refEnd="S3" length="8">
                  <CircPipe diameter="200" />
                </Pipe>
              </PipeNetwork>
            </LandXML>
            """
        ).strip(),
        encoding="utf-8",
    )

    data = network_from_xml(xml)
    storm = data["networks"]["Storm"]

    assert "epsg_code" not in data
    assert "wkt_crs" not in data
    assert set(storm["nodes"]) == {"S1", "S2", "S3"}
    assert set(storm["links"]) == {"P1"}
    assert storm["links"]["P1"]["roughness"] == 0.013


def test_landxml_parsers_reject_entity_expansion(tmp_path):
    TIN, _Triangle, surface_names = tin_helpers()
    xml = tmp_path / "malicious.xml"
    xml.write_text(
        """<!DOCTYPE data [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
        <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">&xxe;</LandXML>
        """,
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        network_from_xml(xml)
    with pytest.raises(Exception):
        surface_names(xml)
    with pytest.raises(Exception):
        TIN().from_landxml(xml)


def test_stdlib_xml_fallback_parses_landxml_and_rejects_entities(monkeypatch, tmp_path):
    valid = tmp_path / "valid.xml"
    valid.write_text(
        '<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" />',
        encoding="utf-8",
    )
    malicious = tmp_path / "malicious.xml"
    malicious.write_text(
        '<!DOCTYPE data [<!ENTITY xxe "expanded">]><LandXML>&xxe;</LandXML>',
        encoding="utf-8",
    )
    malicious_utf16 = tmp_path / "malicious-utf16.xml"
    malicious_utf16.write_text(
        '<!DOCTYPE data [<!ENTITY xxe "expanded">]><LandXML>&xxe;</LandXML>',
        encoding="utf-16",
    )

    assert _stdlib_parse(valid).getroot().tag.endswith("LandXML")
    with pytest.raises(ValueError, match="DTD and entity declarations"):
        _stdlib_parse(malicious)
    with pytest.raises(ValueError, match="DTD and entity declarations"):
        _stdlib_parse(malicious_utf16)

    real_import = builtins.__import__

    def import_without_defusedxml(name, *args, **kwargs):
        if name == "defusedxml":
            raise ImportError("defusedxml unavailable in QGIS")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_defusedxml)
    assert safe_xml.parse(valid).getroot().tag.endswith("LandXML")
