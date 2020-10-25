#!/usr/bin/env python

import os
import time
from testing_utils import *
import unittest
import glob

from optsail.polars import *

plot=False
try:
    plot = os.environ['PLOT']
except KeyError:
    pass


class TestPolars(unittest.TestCase):
    def setUp(self):
        self.dir = scriptdir + os.path.sep + 'polars'


    def test_get(self):
        polar = Polars(filename=self.dir + os.path.sep + 'vpp_1_16.csv')
        speed = polar.get((1.0, 2.0), (5.0, 6.0, 7.0))
        self.assertEqual((2,3), speed.shape)

     
    def test_get_optimal_ranges(self):
        polar = Polars(filename=self.dir + os.path.sep + 'vpp_1_1.csv')
        ranges = polar.get_optimal_ranges((5.0, 6.0, 7.0))
        self.assertEqual((2, 3, 3), np.asarray(ranges).shape)


    def test_save_plot(self):
        for polar in glob.glob(self.dir + os.path.sep + '*'):
            p = Polars(filename=polar)
            savename = os.path.basename(polar)
            p.save_plot(resultsdir + os.path.sep + os.path.splitext(savename)[0] + '.png')

    @unittest.skipUnless(plot, 'Set PLOT in the environment to run this test')
    def test_plot(self):
        p = Polars(filename=self.dir + os.path.sep + 'vo70.txt')
        p.plot()


if __name__ == "__main__":
    unittest.main()

