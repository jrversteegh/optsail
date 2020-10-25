"""
Grib module

Read data from grib files and provide values from them
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2013, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "Proprietary. All use without explicit permission forbidden"


import os
import glob
import math
import bisect
from datetime import datetime, timedelta, tzinfo
from dateutil import tz
import numpy as np
from scipy import interpolate
import gdal
import gdalconst
import appdirs

import matplotlib as mpl
try:
  import matplotlib.pyplot as plt
except:
  pass

from .classes import Object, Logable, DateTime
from .utils import *
from .environment import Environment

# Prefer exceptions over logging to stderr in gdal library
gdal.SetErrorHandler(None)
gdal.UseExceptions()

_tzutc = tz.tzutc()


class GribError(Exception):
    pass


class GribDataError(GribError):
    pass


class GribRangeError(GribError):
    pass


class GribSpanError(GribError):
    pass


class Layer(Object):

    def __init__(self, *args, **kwargs):
        super(Layer, self).__init__(*args, **kwargs)
        self._t = kwargs['t']
        self._data = kwargs['data']
        self._spline = kwargs['spline']
        self._nodata = kwargs['nodata']


    @property
    def t(self):
        return self._t


    @property
    def data(self):
        return self._data


    @property
    def spline(self):
        return self._spline


    @property
    def nodata(self):
        return self._nodata


    def __getitem__(self, index):
        if index < 0:
            index += 4
        if index == 0:
            return self._t
        elif index == 1:
            return self._data
        elif index == 2:
            return self._spline
        elif index == 3:
            return self._nodata
        else:
            raise IndexError('Layer index out of range: %d' % index)




class Grib(Environment):
    """Environment implementation using grib files"""
    _no_data_value = None
    _save_mem = False
    _clip = None

    def __init__(self, *args, **kwargs):
        super(Grib, self).__init__(*args, **kwargs)
        self._fileset = []
        if 'fileset' in kwargs:
            self._fileset = kwargs['fileset'] 
        elif 'filename' in kwargs:
            self._fileset.append(kwargs['filename'])
        if 'no_data_value' in kwargs:
            self._no_data_value = kwargs['no_data_value']
        if 'clip' in kwargs:
            self._clip = kwargs['clip']
        if 'save_mem' in kwargs:
            self._save_mem = bool(kwargs['save_mem'])
        self.reset()
        self.update()


    def _mesh_from_transform(self, tr, xsize, ysize):
        # Setup mesh from the geo transform info and raster size
        minx, xstep, dum1, maxy, dum2, ystep = from_degs(tr)
        if ystep >= 0:
            raise GribDataError('Expected negative ystep from gdal')
        # Transformation looks cell boundary based. We want it cell center based, so shift
        # half a step
        minx += 0.5 * xstep
        maxy += 0.5 * ystep
        maxx = minx + xstep * (xsize - 1)
        miny = maxy + ystep * (ysize - 1)
        # Flip ystep now
        ystep = -ystep

        # Push x range into [-pi, 2pi] range
        if maxx > 2 * math.pi:
            maxx -= 2 * math.pi
            minx -= 2 * math.pi
        if minx < - math.pi:
            maxx += 2 * math.pi
            minx += 2 * math.pi

        # Clip the mesh 
        if self._clip is not None:
            lami, lama, lomi, loma = self._clip
            skipx = int((lomi - minx) / xstep) + 1 if lomi > minx else None
            trimx = int((loma - maxx) / xstep) - 1 if loma < maxx else None
            skipy = int((lami - miny) / ystep) + 1 if lami > miny else None
            trimy = int((lama - maxy) / ystep) - 1 if lama < maxy else None
            self._clip_slice = (slice(skipy, trimy),slice(skipx, trimx))
            self.log.info('Clipping: %s' % str(self._clip_slice))
            if skipx:
                minx += skipx * xstep
                xsize -= skipx
            if trimx:
                maxx += trimx * xstep
                xsize += trimx
            if skipy:
                miny += skipy * ystep
                ysize -= skipy
            if trimy:
                maxy += trimy * ystep
                ysize += trimy

        # If the grib contains data that is wrapped around the earth: repeat the
        # first column at the end
        rangex = maxx - minx
        if rangex > 1.95 * math.pi and rangex < 2 * math.pi:
            xsize += 1
            maxx = minx + xstep * (xsize - 1)
            self._wrap = True
            self.log.info('Wrapping around longitude')
        # Store whether longitude range contains negative values for normalizing
        # angles later
        if minx < 0:
            self._neglon = True
        else:
            self._neglon = False 

        self.log.info('Creating mesh: %s' % \
                      str((miny, maxy, ysize, minx, maxx, xsize)))
        result = np.mgrid[miny:maxy:ysize*1j, minx:maxx:xsize*1j]
        self.log.info('Mesh shape: %s' % str(result.shape))
        return result 


    def _splinefunc_from_array(self, a):
        xs = self._mesh[0][:,0]
        ys = self._mesh[1][0,:]
        # Check if the array contains interlaced data and setup slices to 
        # filter out the rows and columns with "nodata"
        # ...typically 9999
        nodata = np.fabs(a) > 1000
        interlaced = False
        has_nodata = nodata.any()
        if has_nodata:
            self.log.debug('Grib contains NODATA values')
            sx = np.s_[::1]
            sy = np.s_[::1]
            if nodata[1::2,:].all():
                interlaced = True
                sx = np.s_[0::2]
                self.log.info('Grib data is vertically interlaced from 1')
            elif nodata[::2,:].all():
                interlaced = True
                sx = np.s_[1::2]
                self.log.info('Grib data is vertically interlaced from 0')
            if nodata[:,1::2].all():
                interlaced = True
                sy = np.s_[0::2]
                self.log.info('Grib data is horizontally interlaced from 1')
            elif nodata[:,::2].all():
                interlaced = True
                sy = np.s_[1::2]
                self.log.info('Grib data is horizontally interlaced from 0')
            # Map all individual "nodata" values to 0. It's the best we can do
            a *= ~nodata
            if not interlaced:
                # Do some antialiasing to improve interpolation
                self.log.debug('Antialiasing grib NODATA values')
                stamp = np.zeros_like(a)
                fa = 0.4
                stamp[ 1:  , 1:  ]  += a[  :-1,  :-1]
                stamp[ 1:  ,  :-1]  += a[  :-1, 1:  ]
                stamp[  :-1, 1:  ]  += a[ 1:  ,  :-1]
                stamp[  :-1,  :-1]  += a[ 1:  , 1:  ]
                # Add the stamp to add with the nodata mask applied
                a += fa * stamp * nodata

        splined_nd = None
        if interlaced:
            result = interpolate.RectBivariateSpline(xs[sx], ys[sy], a[sx, sy])
            if has_nodata:
                splined_nd = interpolate.RectBivariateSpline(xs[sx], ys[sy], nodata[sx, sy])
        else:
            result = interpolate.RectBivariateSpline(xs, ys, a)
            if has_nodata:
                splined_nd = interpolate.RectBivariateSpline(xs, ys, nodata)
        return result, splined_nd


    def load_from_file(self, filename):
        for action in self.load_from_file_async(filename):
            self.log.info('Performend load action: %s' % action)


    def load_from_file_async(self, filename):
        self.log.info('Attempting to open: %s' % filename)
        data = gdal.Open(filename, gdalconst.GA_ReadOnly)
        self.log.info('Opened: %s of Type: %s' % \
                      (data.GetDescription(), data.GetDriver().LongName))
        if not filename in self._fileset:
            self._fileset.append(filename)

        # Fetch or check the range and resolution of the data in the file
        tr = data.GetGeoTransform()
        if self._origin_and_step is None:
            self._origin_and_step = tr
            self.log.info('Set origin and step: %s' % str(tr))
            self._mesh = self._mesh_from_transform(tr, data.RasterXSize, data.RasterYSize)
        else:
            if tr != self._origin_and_step:
                raise GribDataError('Expected grib file to contain data on matching grid')

        yield DateTime()

        # Get each layer/band of data from the file and store it when we're
        # interested
        for i in range(1, data.RasterCount + 1):
            b = data.GetRasterBand(i)
            md = b.GetMetadata_Dict()
            self.log.debug('Found: %s' % str(md))
            layers = None
            e = md['GRIB_ELEMENT']
            if e == 'UGRD':
                layers = self._wu
            elif e == 'VGRD':
                layers = self._wv
            elif e == 'UOGRD':
                layers = self._cu
            elif e == 'VOGRD':
                layers = self._cv
            if layers is not None:
                times = [i[0] for i in layers]
                self.log.info('Reading: %s' % str(md))
                if not md['GRIB_UNIT'] == '[m/s]':
                    raise GribDataError('Presently only m/s data is supported for velocity')
                ta = md['GRIB_VALID_TIME'].split()
                if not len(ta) == 3 or not ta[1] == 'sec' or not ta[2] == 'UTC':
                    raise GribDataError('Presently only UTC timestamp is supported for time')
                t = DateTime(float(ta[0]), tzinfo=_tzutc)
                self.log.info('Layer time: %s' % str(t))
                # For some reason the y (latitude) range is inverted. Flip it up so 
                # y values are increasing (required for interpolation)
                a = np.flipud(b.ReadAsArray())
                # When wrapped: repeat the first column at the end
                if self._wrap:
                    a = np.hstack((a, a[:,0][np.newaxis,:].T))
                if self._clip is not None:
                    a = a[self._clip_slice]
                f, n = self._splinefunc_from_array(a)
                # Don't keep the original grib data when we need to save memory
                if self._save_mem:
                    a = None
                layer = Layer(t=t, data=a, spline=f, nodata=n)
                i = bisect.bisect_left(times, t)
                if i < len(times) and t == times[i]:
                    self.log.info('Replacing existing layer at %d' % i)
                    layers[i] = layer
                else:
                    self.log.info('Inserting layer at %d' % i)
                    layers.insert(i, layer)

                yield DateTime()

        self.log.info('Read file. Range is now %s, %s, %s, %s and time span is %s, %s' % \
                      (self.range + self.span))


    def update(self):
        for action in self.update_async():
            self.log.info('Performend update action: %s' % action)


    def update_async(self):
        self.log.info('Updating grib set')
        if not self._fileset:
            self.log.warning('No files in fileset')
        for filename in self._fileset:
            if os.path.exists(filename):
                for action in self.load_from_file_async(filename):
                    yield
            else:
                self.log.warning('%s doesn''t exist')


    def prune(self, older_than=timedelta(hours=24)):
        now = DateTime()
        threshold = now - older_than
        for layers in (self._wu, self._wv, self._cu, self._cv):
            while layers: 
                t = layers[0][0]
                if t < threshold:
                    self.log.info('Pruning layer 0 with t: %s' % str(t))
                    del layers[0]
                else:
                    break


    def reset(self):
        self._origin_and_step = None   # Grib file mesh origin and step
        self._clip_slice = None        # Slice determined for clipping
        self._mesh = None    # Full mesh with coordinates
        self._wrap = False   # Whether wrapped around the earth
        self._wu = []        # List with wind u data
        self._wv = []        # List with wind v data
        self._cu = []        # List with current u data
        self._cv = []        # List with current v data
        self._neglon = False # Whether grib contains negative longitudes

    
    def _range_check(self, lats, lons):
        lami, lama, lomi, loma = self.range
        # Range check
        latmin = lats < lami
        latmax = lats > lama
        lonmin = lons < lomi
        lonmax = lons > loma
        if self._no_data_value is None:
            # Raise an error on out of range domain value
            if latmin.any() or latmax.any():
                raise GribRangeError('Latitude(s) out of range: %s' % \
                                     np.compress(latmin + latmax, lats))
            if lonmin.any() or lonmax.any():
                raise GribRangeError('Longitude(s) out of range: %s' % \
                                     np.compress(lonmin + lonmax, lons))
        # Addition of bool arrays acts like boolean "or"
        return latmin + latmax + lonmin + lonmax


    def _apply_range(self, angles, speeds, out_range):
        if self._no_data_value is not None and out_range.any():
            nout_range = ~out_range
            angles *= nout_range
            speeds *= nout_range
            speeds += self._no_data_value * out_range
        return angles, speeds


    def _parse_params(self, positions, time, layers):
        if not layers:
            raise GribDataError('No data in grib')
        times = [i[0] for i in layers]
        ps = np.asarray(positions)
        if ps.shape[0] != 2:
            lats, lons = ps[:,0], ps[:,1]
        else:
            lats, lons = ps[0], ps[1]
        negs = lons < 0
        if not self._neglon and negs.any():
            lons += negs * 2 * math.pi

        # When the grib data doesn't contain negative longitudes, force
        # all longitudes to be positive
        if not self._neglon:
            lons += (lons < 0) * 2 * math.pi
        # Attempt to get time index and fraction. This could be optimized
        ti = bisect.bisect(times, time)
        if ti == 0 or ti == len(times):
            first = times[0]
            last = times[-1]
            raise GribSpanError('Time %s out of range %s - %s' % (time, first, last))
        t0 = times[ti - 1]
        t1 = times[ti]
        tf = (time - t0).total_seconds() / (t1 - t0).total_seconds()  
        return lats, lons, ti, tf


    def _time_interpol(self, layers, index, fraction, lats, lons):
        v0 = layers[index - 1][2].ev(lats, lons)
        v1 = layers[index][2].ev(lats, lons)
        return fraction * v1 + (1 - fraction) * v0


    def _get_wind(self, positions, time):
        """Implementation of Environment._get_wind"""
        lats, lons, ti, tf = self._parse_params(positions, time, self._wu)
        out_range = self._range_check(lats, lons)
        u = self._time_interpol(self._wu,  ti, tf, lats, lons)
        v = self._time_interpol(self._wv,  ti, tf, lats, lons)
        angles = np.arctan2(u, v) + math.pi
        speeds = np.sqrt(u * u + v * v)
        angles, speeds = self._apply_range(angles, speeds, out_range)
        return angles, speeds


    def _get_current(self, positions, time, filter_nodata=False):
        """Implementation of Environment._get_current"""
        lats, lons, ti, tf = self._parse_params(positions, time, self._cu)
        out_range = self._range_check(lats, lons)
        u = self._time_interpol(self._cu,  ti, tf, lats, lons)
        v = self._time_interpol(self._cv,  ti, tf, lats, lons)
        angles = np.arctan2(u, v)
        # Arctan2 range is [-pi, pi) and we want [0, 2pi)
        angles += (angles < 0) * 2 * math.pi
        speeds = np.sqrt(u * u + v * v)
        if filter_nodata:
            splined_nd = self._cu[ti][3]
            if splined_nd is not None:
                have_data = splined_nd.ev(lats, lons) < 0.35
                angles *= have_data
                speeds *= have_data
                if self._no_data_value:
                    speeds += ~have_data * self._no_data_value
        angles, speeds = self._apply_range(angles, speeds, out_range)
        return angles, speeds


    @property
    def range(self):
        if self._mesh is not None:
            return (self._mesh[0][0, 0], self._mesh[0][-1, -1],
                    self._mesh[1][0, 0], self._mesh[1][-1, -1])
        else:
            return (0., 0., 0., 0.)


    @property
    def span(self):
        if self._wu:
            return (self._wu[0][0], self._wu[-1][0] - self._wu[0][0])
        elif self._cu:
            return (self._cu[0][0], self._cu[-1][0] - self._cu[0][0])
        else:
            return (DateTime.utcnow(), timedelta(0))


    @property
    def no_data_value(self):
        return self._no_data_value

    @no_data_value.setter
    def no_data_value(self, value):
        self._no_data_value = value


    def _plot(self, t):
        # TODO Create a vector plot / animation
        pass


    def save_plot(self, filename, t):
        self._plot(t)
        try:
            plt.savefig(filename)
        except NameError as e:
            self.log.warning('MatplotLib not working')


    def plot(self, t):
        self._plot(t)
        plt.show()
        


class LiveGrib(Grib):
    _update_file = ''
    _update_file_default = 'updated'
    _updated = 0

    def __init__(self, *args, **kwargs):
        super(LiveGrib, self).__init__(*args, **kwargs)
        self._update_stamp()


    def check(self):
        if self._should_update():
            self.update()


    def check_async(self):
        if self._should_update():
            for action in self.update_async():
                yield action
        else:
            return iter(())


    def load_from_file_async(self, filename):
        self.log.debug('Loading: %s' % filename)
        for action in Grib.load_from_file_async(self, filename):
            yield action
        self._update_stamp()

    
    def _update_update_file(self):
        if not self._update_file:
            self._update_file = self._update_file_default
            self.log.info('Update file is now: %s' % self._update_file)
        if self._fileset: 
            try:
                self._update_file.index(os.path.sep)
            except ValueError:
                filedir = os.path.dirname(self._fileset[0])
                self._update_file = filedir + os.path.sep + self._update_file
                self.log.info('Update file is now: %s' % self._update_file)


    def _update_stamp(self):
        self._update_update_file()
        if os.path.exists(self._update_file):
            self._updated = os.path.getmtime(self._update_file)
        else:
            self.log.warning('Update file "%s" does not exist' % self._update_file)
            self._updated = 0


    def _should_update(self):
        self._update_update_file()
        if os.path.exists(self._update_file):
            return os.path.getmtime(self._update_file) > self._updated
        else:
            return False


    @property
    def updated(self):
        return self._updated


    def update_async(self):
        for action in super(LiveGrib, self).update_async():
            yield action
        self.prune()



class GFS(LiveGrib):

    _update_file_default = 'updated.gfs'

    def __init__(self, *args, **kwargs):
        if not 'filedir' in kwargs:
            kwargs['filedir'] = appdirs.user_cache_dir('gribs')
        kwargs['fileset'] = glob.glob(kwargs['filedir'] + '/gfs*')
        if not 'update_file' in kwargs:
            kwargs['update_file'] = 'updated.gfs'
        super(GFS, self).__init__(*args, **kwargs)
        self.log.info('Looked for files in %s' % kwargs['filedir'])



class GEFS(LiveGrib):

    _update_file_default = 'updated.gefs'

    def __init__(self, *args, **kwargs):
        if not 'filedir' in kwargs:
            kwargs['filedir'] = appdirs.user_cache_dir('gribs')
        if not 'set' in kwargs:
            kwargs['set'] = 0
        filebase = 'gefs-%.2d-*' % kwargs['set']
        kwargs['fileset'] = glob.glob(kwargs['filedir'] + '/' + filebase)
        if not 'update_file' in kwargs:
            kwargs['update_file'] = 'updated.gefs'
        super(GEFS, self).__init__(*args, **kwargs)



class BSH(LiveGrib):

    _update_file_default = 'updated.bsh'

    def __init__(self, *args, **kwargs):
        if not 'filedir' in kwargs:
            kwargs['filedir'] = appdirs.user_cache_dir('gribs')
        kwargs['fileset'] = glob.glob(kwargs['filedir'] + self._set_pattern)
        super(BSH, self).__init__(*args, **kwargs)



class BSHNorthSea(BSH):

    _set_pattern = '/Current_no_*'



class BSHGermanBight(BSH):

    _set_pattern = '/Current_db_*'



class BSHBaltic(BSH):

    _set_pattern = '/Current_ba_*'



class BSHWestBaltic(BSH):

    _set_pattern = '/Current_wb_*'
