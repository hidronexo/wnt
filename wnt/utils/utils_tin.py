"""TIN interpolation utilities for LandXML surfaces."""

from .safe_xml import parse as safe_xml_parse

from qgis.core import (QgsFeature,
                       QgsGeometry,
                       QgsRectangle,
                       QgsSpatialIndex)

ACCEPTABLE_DEVIATION = 1E-5
DEGENERATE_DETERMINANT_TOLERANCE = 1E-12
LANDXML_NAMESPACES = {
    'http://www.landxml.org/schema/LandXML-1.0',
    'http://www.landxml.org/schema/LandXML-1.1',
    'http://www.landxml.org/schema/LandXML-1.2',
}
VERTICES_PER_FACE = 3


def _local_name(tag):
    return tag.rsplit('}', 1)[-1]


def _landxml_namespace(root):
    """Return and validate the namespace declared by a LandXML root."""
    if _local_name(root.tag) != 'LandXML':
        raise ValueError('Invalid LandXML file: expected LandXML root.')
    if not root.tag.startswith('{'):
        return ''
    namespace = root.tag[1:].split('}', 1)[0]
    if namespace not in LANDXML_NAMESPACES:
        raise ValueError(f'Unsupported LandXML namespace: {namespace}')
    return namespace


def xmlname(namespace, name):
    return f'{{{namespace}}}{name}' if namespace else name


def surface_names(file):
    """Return LandXML TIN surface names in file order."""
    tree = safe_xml_parse(file)
    root = tree.getroot()
    namespace = _landxml_namespace(root)
    names = []
    for surface in root.iter(xmlname(namespace, 'Surface')):
        definition = surface.find(xmlname(namespace, 'Definition'))
        if definition is None or definition.attrib.get('surfType') != 'TIN':
            continue
        names.append(surface.attrib.get('name', ''))
    return names

class Triangle:
    '''Triangle defined for 3 points, (xi, yi, zi).'''
    def __init__(self, p1, p2, p3):
        self.v1 = p1
        self.v2 = p2
        self.v3 = p3

    def xy_area(self):
        '''Calculate the XY area.'''
        ax = self.v2[0] - self.v1[0]
        ay = self.v2[1] - self.v1[1]
        bx = self.v3[0] - self.v1[0]
        by = self.v3[1] - self.v1[1]
        return abs(ax*by - ay*bx)/2

    def bounding_box(self):
        '''Return the XY bounding box.'''
        xs = (self.v1[0], self.v2[0], self.v3[0])
        ys = (self.v1[1], self.v2[1], self.v3[1])
        return QgsRectangle(min(xs), min(ys), max(xs), max(ys))

    def is_degenerate(self, tol=DEGENERATE_DETERMINANT_TOLERANCE):
        '''Check if the triangle has usable XY area.'''
        return self.xy_area() <= tol/2

    def is_inside(self, point, tol=ACCEPTABLE_DEVIATION):
        '''Check if the point (x, y) is inside.'''
        a = self.xy_area()
        tmp = Triangle(self.v1, self.v2, point)
        a -= tmp.xy_area()
        tmp = Triangle(self.v3, self.v2, point)
        a -= tmp.xy_area()
        tmp = Triangle(self.v3, self.v1, point)
        a -= tmp.xy_area()
        return abs(a) <= tol

    def z(self, point):
        '''Return z corresponding to the point (x, y).'''
        a = self.v2[0] - self.v1[0]
        b = self.v2[1] - self.v1[1]
        c = self.v3[0] - self.v1[0]
        d = self.v3[1] - self.v1[1]
        e = self.v2[2] - self.v1[2]
        f = self.v3[2] - self.v1[2]
        det = a*d - b*c
        if abs(det) <= DEGENERATE_DETERMINANT_TOLERANCE:
            raise ValueError('Cannot interpolate elevation from a degenerate triangle.')
        jx = (d*e - b*f)/det
        jy = (-c*e + a*f)/det
        dx = point[0] - self.v1[0]
        dy = (point[1] - self.v1[1])
        return jx*dx + jy*dy + self.v1[2]


class TIN:
    '''TIN surface.'''
    def __init__(self):
        self._faces = []
        self._points = {}
        self._triangles = []
        self._spatial_index = QgsSpatialIndex()
        self.surface_name = ''
        self.crs_authid = ''
        self.crs_wkt = ''

    def from_landxml(self, file, surfname=''):
        '''Load a TIN surface from a LandXML file.

        Parameters
        ----------
        file, string, is the LandXML file name
        surfname, string, is the surface name, by default load the first one
        '''
        tree = safe_xml_parse(file)
        root = tree.getroot()
        namespace = _landxml_namespace(root)
        coordinate_system = root.find(xmlname(namespace, 'CoordinateSystem'))
        crs_authid = ''
        crs_wkt = ''
        if coordinate_system is not None:
            crs_authid = str(coordinate_system.attrib.get('epsgCode') or '').strip()
            if crs_authid.isdigit():
                crs_authid = f"EPSG:{crs_authid}"
            crs_wkt = str(coordinate_system.attrib.get('ogcWktCode') or '').strip()
        available_surfaces = []
        for surface in root.iter(xmlname(namespace, 'Surface')):
            surface_name = surface.attrib.get('name', '')
            available_surfaces.append(surface_name)
            definition = surface.find(xmlname(namespace, 'Definition'))
            if definition is None or definition.attrib.get('surfType') != 'TIN':
                continue
            if surfname != '' and surfname != surface_name:
                continue
            points = definition.find(xmlname(namespace, 'Pnts'))
            faces = definition.find(xmlname(namespace, 'Faces'))
            if points is None or faces is None:
                continue

            # Build the surface locally so a failed load cannot leave partial state.
            new_points = {}
            new_faces = []
            for point in points:
                y, x, z = tuple(map(float, point.text.split()))
                new_points[point.attrib['id']] = x, y, z
            for face in faces:
                vertices = face.text.split()
                if len(vertices) != VERTICES_PER_FACE:
                    raise ValueError('TIN faces must reference exactly three points.')
                new_faces.append(vertices)

            # Precompute validated triangles once; interpolation can reuse them.
            new_triangles = []
            new_spatial_index = QgsSpatialIndex()
            for face in new_faces:
                vertices = [new_points[vertex] for vertex in face]
                triangle = Triangle(*vertices)
                if triangle.is_degenerate():
                    raise ValueError('TIN faces must have non-zero XY area.')

                feature = QgsFeature()
                feature.setId(len(new_triangles))
                feature.setGeometry(QgsGeometry.fromRect(triangle.bounding_box()))
                new_spatial_index.addFeature(feature)
                new_triangles.append(triangle)

            self._points = new_points
            self._faces = new_faces
            self._triangles = new_triangles
            self._spatial_index = new_spatial_index
            self.surface_name = surface.attrib.get('name', '')
            self.crs_authid = crs_authid
            self.crs_wkt = crs_wkt
            break
        else:
            available = ', '.join(name or '<unnamed>' for name in available_surfaces)
            if available:
                raise ValueError(
                    f'Requested TIN surface was not found. Available surfaces: {available}'
                )
            raise ValueError('Requested TIN surface was not found. No surfaces were found.')

    def elevations(self, points):
        '''Return elevations [z1,..] from points [(x1, y1)..].
        '''
        result = []
        for p in points:
            candidates = self._spatial_index.intersects(QgsRectangle(p[0], p[1], p[0], p[1]))
            for triangle_id in candidates:
                triangle = self._triangles[triangle_id]
                if triangle.is_inside(p):
                    result.append(triangle.z(p))
                    break
            else:
                result.append(None)
        return result
