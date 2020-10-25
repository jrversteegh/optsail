#!/usr/bin/env python

import os
import time
import sys
import math
import subprocess
from datetime import datetime, timedelta
from testing_utils import *
import unittest
import objgraph

from optsail.grib import *
from optsail.utils import *
from optsail.classes import *

plot=False
try:
    plot = os.environ['PLOT']
except KeyError:
    pass

gribdir = scriptdir + '/gribs'
def gribs_required(filename,  maxage, scriptarg):
    def wrap(fun):
        def decorated(*args, **kwargs):
            grb = gribdir + '/' + filename
            if not file_exists(grb) or file_age(grb) > maxage:
                subprocess.check_call(scriptdir + '/get_gribs.sh ' + scriptarg, shell=True)
            fun(*args, **kwargs)
        return decorated
    return wrap


def touch(fname):
    try:
        os.utime(fname, None)
    except:
        open(fname, 'a').close()


class TestGrib(unittest.TestCase):
    @gribs_required('gfs-000.grb2', maxage=172800, scriptarg='wind')
    def test_get_wind(self):
        # World wind tomorrow
        g = Grib(filename=gribdir + '/gfs-000.grb2')
        for i in range(4, 76, 4):
            g.load_from_file(gribdir + '/gfs-%03d.grb2' % i)
        # Position on the north sea somewhere north west of Texel
        t = DateTime() + timedelta(hours=12)
        try:
            a, r = g.get_wind((from_degs((53., 4.)), 
                               from_degs((54., 4.)),
                               from_degs((55., 4.)),
                               from_degs((56., 4.)),
                              ), t)
        except GribRangeError as e:
            log.error('Loaded gens wind grib but data was out of range')
            self.assertTrue(False, str(e))
        else:    
            log.info('====> GFS Wind 53,4 %s %s %s', t, a[0], r[0])
            log.info('====> GFS Wind 54,4 %s %s %s', t, a[1], r[1])
            log.info('====> GFS Wind 55,4 %s %s %s', t, a[2], r[2])
            log.info('====> GFS Wind 56,4 %s %s %s', t, a[3], r[3])
            

    @gribs_required('gfs-000.grb2', maxage=172800, scriptarg='wind')
    def test_update(self):
        g = Grib(filename=gribdir + '/gfs-000.grb2')
        g.load_from_file(gribdir + '/gfs-004.grb2')
        self.assertEqual(2, len(g._wu))
        t0 = g._wu[0][0]
        t1 = g._wu[1][0]
        g.update()
        self.assertEqual(2, len(g._wu))
        self.assertEqual(t0, g._wu[0][0])
        self.assertEqual(t1, g._wu[1][0])

    @gribs_required('gfs-000.grb2', maxage=172800, scriptarg='wind')
    def test_update_async(self):
        g = Grib(filename=gribdir + '/gfs-000.grb2')
        i = 0
        for action in g.load_from_file_async(gribdir + '/gfs-004.grb2'):
            i += 1
        self.assertEqual(2, len(g._wu))
        t0 = g._wu[0][0]
        t1 = g._wu[1][0]
        for action in g.update_async():
            i += 1
        self.assertEqual(2, len(g._wu))
        self.assertEqual(i, 9)
        self.assertEqual(t0, g._wu[0][0])
        self.assertEqual(t1, g._wu[1][0])


    @gribs_required('Current_no_today.grb2', maxage=172800, scriptarg='current')
    def test_get_current(self):
        # Northsea current tomorrow
        g = Grib(filename=gribdir + '/Current_no_today.grb2')
        g.load_from_file(filename=gribdir + '/Current_no_today_plusone.grb2')
        g.load_from_file(filename=gribdir + '/Current_no_today_plustwo.grb2')
        # Position on the north sea somewhere north west of Texel
        t = DateTime()
        try:
             U = g.get_current((from_degs((53., 4.)), from_degs((54., 4.)),
                                from_degs((55., 4.)), from_degs((56., 4.))), t)
             a, r = U
        except GribRangeError as e:
            log.error('Loaded current grib but data was out of range')
            self.assertTrue(False, str(e))
        else:
            log.info('Current 53,4 %s %s %s', t, a[0], r[0])
            log.info('Current 54,4 %s %s %s', t, a[1], r[1])
            log.info('Current 55,4 %s %s %s', t, a[2], r[2])
            log.info('Current 56,4 %s %s %s', t, a[3], r[3])


    def test_svasek(self):
        g = Grib(filename=scriptdir + '/files/Rio_20140106.grb')
        t = DateTime('2014-01-06 02:00')
        U = g.get_current((from_degs((-22.9, -43.15)),), t)
        a, r = U
        log.info('Current in Rio bay: %s %s', a, r)


    @gribs_required('Current_no_today.grb2', maxage=172800, scriptarg='current')
    def test_range(self):
        g = Grib(filename=gribdir + '/Current_no_today.grb2')
        g.load_from_file(filename=gribdir + '/Current_no_today_plusone.grb2')
        g.load_from_file(filename=gribdir + '/Current_no_today_plustwo.grb2')
        log.info('Current North Sea range: %s' % str(to_degs(g.range)))
        log.info('Current North Sea span: %s' % str(g.span))
        t = DateTime()
        # This is not on the north sea. Expect a range error
        self.assertRaises(GribRangeError, g.get_current, from_degs((20.0, 4.5))[np.newaxis,:], t)
        # ... except when we set no_data_value
        g.no_data_value = -1.0
        a, r = g.get_current(from_degs((20.0, 4.5)), t)
        log.info('Out of range current: %s, %s', a, r)
        self.assertTrue((r == -1.0).all(), 'Expected velocity to be "no_data_value"')
        self.assertTrue((a == 0.0).all(), 'Expected angle to be 0.0 on out of range')


    @gribs_required('Current_no_today.grb2', maxage=172800, scriptarg='current')
    def test_filter_nodata(self):
        g = Grib(filename=gribdir + '/Current_no_today.grb2')
        g.load_from_file(filename=gribdir + '/Current_no_today_plusone.grb2')
        log.info('Current North Sea range: %s' % str(to_degs(g.range)))
        log.info('Current North Sea span: %s' % str(g.span))
        t = DateTime()
        g.no_data_value = -1.0
        # This location is exactly the beach line of Hoek van Holland
        pos = from_degs((52.0, 4.12))
        a, r = g.get_current(pos, t)
        log.info('Out of range current (not filtered): %s, %s', a, r)
        self.assertTrue((r > 0.0).all(), 'Expected velocity to be greater then zero')
        splined_nd = g._cu[0][3]
        frac = splined_nd.ev(*pos)
        log.info('Nodata frac: %s' % frac)
        a, r = g.get_current(pos, t, filter_nodata=True)
        log.info('Out of range current (filtered): %s, %s', a, r)
        self.assertTrue((r == -1.0).all(), 'Expected velocity to be "no_data_value"')
        self.assertTrue((a == 0.0).all(), 'Expected angle to be 0.0 for nodata')


    @gribs_required('Current_no_today.grb2', maxage=172800, scriptarg='current')
    @gribs_required('gfs-000.grb2', maxage=172800, scriptarg='wind')
    def test_interpol_error(self):
        ''' 
        Test evaluation at exactly the mesh points to verify that the
        interpolation returns the exact values at mesh points
        '''
        def do_test(grib, ulayer, vlayer, getter, rot=0):
            m = grib._mesh
            # Only consider first two layers
            u1 = ulayer[0]
            u2 = ulayer[1]
            v1 = vlayer[0]
            v2 = vlayer[1]
            t = u1[0] + (u2[0] - u1[0]) * 0.5
            self.assertEqual(u2[0], v2[0], 'Expected times of u and v to be the same')
            self.assertEqual(m[0].shape, u1[1].shape, 'Expected data and mesh to have similar shape')
            ud = (0.5 * (u1[1] + u2[1])).flatten()
            vd = (0.5 * (v1[1] + v2[1])).flatten()
            las = m[0].flatten()
            los = m[1].flatten()
            self.assertEqual(las.shape, ud.shape, 'lat''s and u''s to have the same shape')
            a, r = getter((las, los), t)
            u = np.sin(a + rot) * r
            v = np.cos(a + rot) * r
            du = np.fabs(u - ud)
            dv = np.fabs(v - vd)
            mxu = np.max(du)
            mxui = np.argmax(du)
            mxv = np.max(dv)
            mxvi = np.argmax(dv)
            log.info('Max u difference: %s at %s' % (mxu, mxui))
            log.info('Max v difference: %s at %s' % (mxv, mxvi))
            self.assertLess(mxu, 1E-6, 'Expected u diff to be small')
            self.assertLess(mxv, 1E-6, 'Expected v diff to be small')

        g = Grib(filename=gribdir + '/gfs-000.grb2')
        g.load_from_file(gribdir + '/gfs-004.grb2')
        log.info('*** Test wind interpol')
        do_test(g, g._wu, g._wv, g.get_wind, math.pi)
        g = Grib(filename=gribdir + '/Current_no_today.grb2')
        log.info('*** Test current interpol')
        do_test(g, g._cu, g._cv, g.get_current)


    @gribs_required('gfs-072.grb2', maxage=172800, scriptarg='wind')
    def test_clip(self):
        log.info('*** Test grib clipping')
        clip = from_degs([40,60,0,20])
        log.info('Clip to set: %s' % str(clip))
        g = Grib(filename=gribdir + '/gfs-000.grb2', clip=clip)
        g.load_from_file(gribdir + '/gfs-024.grb2')
        g.load_from_file(gribdir + '/gfs-048.grb2')
        g.load_from_file(gribdir + '/gfs-072.grb2')
        log.info('Clipped range: %s' % str(to_degs(g.range)))
        t = DateTime() + timedelta(hours=12)
        lalos = (from_degs((53., 56.)), from_degs((4., 4.)))
        a, r = g.get_wind(lalos, t)
        lalos = (from_degs((53., 61.)), from_degs((4., 4.)))
        self.assertRaises(GribError, g.get_wind, lalos, t)




class TestLiveGrib(unittest.TestCase):

    def setUp(self):
        self.g = LiveGrib(filedir=gribdir)
        for i in range(0, 76, 4):
            self.g.load_from_file(gribdir + '/gfs-%03d.grb2' % i)

    def test_check(self):
        # World wind tomorrow
        log.info('=== Check 1')
        self.g.check()
        u1 = self.g.updated
        touch(gribdir + '/updated')
        log.info('=== Check 2')
        self.g.check()
        u2 = self.g.updated
        log.info('=== Check 3')
        self.g.check()
        self.assertNotEqual(u1, u2)


    def do_update(self):
        leaked = objgraph.get_leaking_objects()
        self.g.update()
        leaked = objgraph.get_leaking_objects()
        ts = objgraph.typestats(leaked)
        self.assertFalse(ts)


    def test_update(self):
        for i in range(5):
            self.do_update()


    def test_prune(self):
        c1 = len(self.g._wu)
        self.g.prune(timedelta())
        c2 = len(self.g._wu)
        self.assertLess(c2, c1)


        


if __name__ == "__main__":
    unittest.main()

