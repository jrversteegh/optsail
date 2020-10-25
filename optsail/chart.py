"""
Chart module

Interface for providing geographical / nautical information
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2015, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "Proprietary. All use without explicit permission forbidden"

import os
from datetime import datetime

import numpy as np

from .utils import to_degs

try:
    from osgeo import ogr
except ImportError:
    ogr = None


from .classes import Object, Logable
from .data import get_data_dir

class LandPolygons(Logable):
    _land_polygon_driver = None
    _land_polygon_layer = None
    _land_polygon_data_source = None

    @classmethod
    def _get_layer(cls, log):
        if not ogr:
            log.warning('OSGEO OGR not available. gdal not installed?')
            return None
        if cls._land_polygon_layer:
            return cls._land_polygon_layer
        try:
            cls._land_polygon_driver = ogr.GetDriverByName('ESRI Shapefile')
        except NameError:
            pass
        if cls._land_polygon_driver is None:
            log.warning('OSGEO OGR ESRI shapefile driver not available.')
            return None
        land_polygons = get_data_dir() + '/charts/land_polygons/land_polygons.shp'
        if not os.path.exists(land_polygons):
            log.warning('Land polygon file doesn''t exist: %s' % land_polygons)
        cls._land_polygon_data_source = cls._land_polygon_driver.Open(land_polygons, 0)
        if cls._land_polygon_data_source is not None:
            cls._land_polygon_layer = cls._land_polygon_data_source.GetLayer()
            return cls._land_polygon_layer
        else:
            log.warning('Failed to create land polygon data source')
            return None


    def get_layer(self):
        return self._get_layer(self.log)



land_polygons = LandPolygons()



class Chart(Logable):
    def __init__(self, *args, **kwargs):
        super(Chart, self).__init__(*args, **kwargs)

    def water_depth(self, positions, time=None):
        if time is None:
            time = datetime.utcnow()
        if not isinstance(positions, tuple) and not isinstance(positions, list):
            positions = (positions,)
        return self._water_depth(positions, time)

    def is_navigable(self, lines, draft=0, time=None):
        if time is None:
            time = datetime.utcnow()
        if not isinstance(lines, tuple) and not isinstance(lines, list):
            lines = (lines,)
        return self._is_navigable(lines, draft, time)

    def is_land(self, positions, time=None):
        return self.water_depths(positions, time) <= 0

    def is_water(self, positions, time=None):
        return self.water_depths(positions, time) > 0

    def _water_depth(self, positions, time):
        '''Default implementation for water_depth: 100m deep everywhere'''
        return np.ones(len(positions)) * 100

    def _is_navigable(self, lines, draft, time):
        '''Default implementation for navigability of tracks segments indicated by lines'''
        layer = land_polygons.get_layer()
        result = np.ones(len(lines), dtype=bool)
        if layer:
            geom = ogr.Geometry(ogr.wkbLineString)
            for line in lines:
                geom.AddPoint(line.p1.lon, line.p1.lat)
                geom.AddPoint(line.p2.lon, line.p2.lat)
            # TODO doesn't work with line crossing 180 longitude
            hull = geom.ConvexHull()
            layer.SetSpatialFilter(hull)
            for feature in layer:
               feature_geom = feature.GetGeometryRef()
               for i, line in enumerate(lines):
                   geom = ogr.Geometry(ogr.wkbLineString)
                   geom.AddPoint(line.p1.lon, line.p1.lat)
                   geom.AddPoint(line.p2.lon, line.p2.lat)
                   if geom.Intersects(feature_geom):
                       result[i] = False

        return result
