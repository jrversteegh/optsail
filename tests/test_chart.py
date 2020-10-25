#!/usr/bin/env python

import os
import time
from testing_utils import *
import unittest
import glob

import geofun
geofun.set_angle_mode('degrees')
from geofun import Position, Line

from optsail.chart import *

plot=False
try:
    plot = os.environ['PLOT']
except KeyError:
    pass

class TestChart(unittest.TestCase):
    def setUp(self):
        self.chart = Chart()

    def test_get_land_polygon_layer(self):
        layer = land_polygons.get_layer()
        self.assertFalse(
            layer is None, 
            'Expected valid polygon layer.\n'
            'Check log for gdal or OPTSAIL_DATA_DIR issue.'
        )
        e = layer.GetExtent()
        self.assertEqual(-180, e[0])
        self.assertEqual(180, e[1])
        self.assertEqual(-90, e[2])
        self.assertAlmostEqual(83.66, e[3], delta=0.01)
        # Select an area crossing 180 degrees latitude
        # FIJI
        self.assertTrue(layer, 'Expected layer to be assigned.  OPTSAIL_DATA_DIR not set?')
        f_count = layer.GetFeatureCount()
        layer.SetSpatialFilterRect(177, -21, 180, -15)
        f1_count = layer.GetFeatureCount()
        layer.SetSpatialFilter(None)
        f2_count = layer.GetFeatureCount()
        layer.SetSpatialFilterRect(-180, -21, -178, -15)
        f3_count = layer.GetFeatureCount()
        layer.SetSpatialFilterRect(177, -21, -178, -15)
        f4_count = layer.GetFeatureCount()
        self.assertEqual(683161, f_count)
        self.assertEqual(598, f1_count)
        self.assertEqual(683161, f2_count)
        self.assertEqual(287, f3_count)
        # Doesn't work :( This got everything except FIJI
        self.assertEqual(9827, f4_count)


    def test_geofun(self):
        p1 = Position(52, -178)
        l1 = Line(p1, Position(51, -177))
        self.assertAlmostEqual(52, l1.p1.lat)
        l2 = Line(Position(48, 178), Position(52, -178))
        self.assertAlmostEqual(131147, l1.v.r, delta=1)
        self.assertAlmostEqual(529213, l2.v.r, delta=1)


    def test_navigable(self):
        # Check dutch coastline just north of Hoek van Holland
        l_miss = Line(Position(52.1, 4.122), Position(52.01, 4.122))
        l_hit = Line(Position(52.01, 4.122), Position(52.00, 4.124))
        n_miss = self.chart.is_navigable(l_miss)[0]
        self.assertTrue(n_miss)
        n_hit = self.chart.is_navigable(l_hit)[0]
        self.assertFalse(n_hit)
        r = self.chart.is_navigable((l_miss, l_hit))
        n_miss = r[0]
        n_hit = r[1]
        self.assertTrue(n_miss)
        self.assertFalse(n_hit)


if __name__ == "__main__":
    unittest.main()

