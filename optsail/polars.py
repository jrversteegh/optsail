"""
Polars module

Read boat polar data from file
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2013, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "Proprietary. All use without explicit permission forbidden"


import os
import math
import numpy as np
from scipy import interpolate

import matplotlib as mpl
import matplotlib.pyplot as plt

from classes import Object, OptsailError
from utils import *


class Polars(Object):

    _title = ''

    def __init__(self, *args, **kwargs):
        super(Polars, self).__init__(*args, **kwargs)
        try:
            self._smoothing = kwargs['smoothing']
        except KeyError:
            self._smoothing = None

        try:
            self._degree = kwargs['degree']
        except KeyError:
            self._degree = None

        try:
            self._filename = kwargs['filename']
            self.load_from_file()

        except KeyError:
            self._filename = 'noname.txt'
            try:
                wind_speeds = kwargs['wind_speeds']
                wind_angles = kwargs['wind_angles']
                boat_speeds = kwargs['boat_speeds']
            except KeyError:
                wind_speeds = np.linspace(0, 50, 11)
                wind_angles = np.linspace(0, np.pi, 19)
                boat_speeds = np.sqrt(wind_speeds) * np.sqrt(1.3 * wind_angles[:,np.newaxis])
            self._from_data(wind_speeds, wind_angles, boat_speeds)


    def _from_data(self, wind_speeds, wind_angles, boat_speeds):
        self._mesh = np.meshgrid(wind_speeds, wind_angles)
        self._data = np.array(boat_speeds).reshape(self._mesh[0].shape)
        self._update_interpolation(self._smoothing, self._degree)


    def _update_interpolation(self, smoothing=None, degree=None):
        if degree is None:
            degree = 3
        if smoothing:
            s = max(len(self._mesh[0][0,:]), len(self._mesh[1][:,0]))
        else:
            s = 0
        self._evaluator = interpolate.RectBivariateSpline(
            self._mesh[1][:,0], self._mesh[0][0,:],
            self._data,
            kx=degree, ky=degree,
            s=s,
        )


    def save_to_file(self, filename=None):
        '''
        Save polars to file in optsail polar data format:
        - Header line with wind speeds
        - Header line with wind angles
        - Number of angles data lines with boatspeed at each wind speed
        '''
        if not filename:
            filename = self._filename
        with open(filename, "w") as f:
            f.write('# Wind speeds\n')
            for speed in self.speeds:
                f.write(' %.2f' % to_kns(speed))
            f.write('\n')
            f.write('# Wind angles\n')
            for angle in self.angles:
                f.write(' %.2f' % to_degs(angle))
            f.write('\n')
            f.write('# Boat speeds\n')
            for r in self.data:
                for c in r:
                    f.write(' %.2f' % to_kns(c))
                f.write('\n')


    def load_from_file(self, filename=None):
        '''
        Load polars from file. Currently three formats are supported:
        1. Header line with wind speeds. Data line starting with angle
           followed by boat speeds
        2. Header line with windspeeds and header line with angles.
           Data lines with boat speeds
        3. Data lines with wind speed followed by pairs of angle and
           boat speed
        Angles are expected in degrees and speeds in knots
        '''
        if not filename:
            filename = self._filename
        self._filename = filename

        wind_speeds = []
        wind_angles = []
        boat_speeds = []
        transpose = True
        no_header = False

        with open(filename, "r") as f:
            for line in f:
                # Replace comma's and semicolons with spaces
                line = line.replace(',', ' ')
                line = line.replace(';', ' ')
                # Strip whitespace and line ends
                line = line.strip()
                # Skip empty lines and comments
                if not line or line[0] == '#' or line[0] == '!' or line[:3] == 'pol':
                    continue
                values = to_float(line.split())
                if len(values) == 0:
                    continue
                if len(wind_speeds) == 0:
                    if np.all(values == np.sort(values)):
                        wind_speeds = from_knots(values)
                        continue
                    else:
                        no_header = True
                if no_header:
                    wind_speeds.append(from_knots(values[0]))
                    wind_angles = from_degs(values[1::2])
                    boat_speeds.append(from_knots(values[2::2]))
                    transpose = True
                    continue
                if len(values) == (len(wind_speeds) + 1):
                    transpose = False
                    wind_angles.append(from_degs(values[0]))
                    boat_speeds.append(from_knots(values[1:]))
                    continue
                if len(wind_angles) == 0:
                    wind_angles = from_degs(values)
                else:
                    if len(values) == len(wind_speeds):
                        transpose = False
                    else:
                        # Fill out incomplete lines with last value
                        if transpose:
                            while len(values) < len(wind_angles):
                                np.append(values, values[-1])
                        else:
                            while len(values) < len(wind_speeds):
                                np.append(values, values[-1])
                    boat_speeds.append(from_knots(values))
            boat_speeds = np.array(boat_speeds)
            if transpose:
                boat_speeds = boat_speeds.transpose()
            self._from_data(wind_speeds, wind_angles, boat_speeds)


    @property
    def mesh(self):
        return self._mesh


    @property
    def data(self):
        return self._data


    @property
    def wind_angles(self):
        return self._mesh[1][:,0]


    @property
    def wind_speeds(self):
        return self._mesh[0][0,:]


    def get(self, angles, wind_speeds=None, squeeze=True):
        if wind_speeds is None:
            angles, wind_speeds = angles
        angles = np.fabs(angles)
        result = self._evaluator(angles, wind_speeds)
        if squeeze:
            result = np.squeeze(result)
        return result


    def get_optimal_ranges(self, wind_speeds):
        angles = from_degs([d for d in range(181)])
        speeds = self.get(angles, wind_speeds, squeeze=False)
        vmg = speeds * np.cos(angles)[:,np.newaxis]
        vmgui = np.argmax(vmg, axis=0)
        vmgdi = np.argmin(vmg, axis=0)
        return (
            np.array((angles[vmgui], np.diag(vmg[vmgui]), np.diag(speeds[vmgui]))),
            np.array((angles[vmgdi], np.diag(vmg[vmgdi]), np.diag(speeds[vmgdi]))),
        )


    def _plot(self, merge):
        if not merge:
            plt.clf()
        max_boat_speed = 0.
        max_wind_speed = 35.
        pp = plt.subplot(111, polar=True)
        knot_wind_speeds = to_knots(self.wind_speeds)
        nm = mpl.colors.Normalize(vmin=0., vmax=max_wind_speed)
        cm = mpl.cm.get_cmap('rainbow')
        sm = mpl.cm.ScalarMappable(norm=nm, cmap=cm)
        sm.set_array(np.linspace(0., max_wind_speed, 20))
        for i, w in enumerate(self.wind_speeds):
            clr = sm.to_rgba(knot_wind_speeds[i])
            knot_boat_speeds = to_knots(self._data[:,i])
            max_boat_speed = max(max_boat_speed, max(knot_boat_speeds))
            plt.plot(-self.wind_angles, knot_boat_speeds, color=clr)
        pp.set_rmax((max_boat_speed // 5 + 1) * 5)
        angles = list(range(-180, 1, 15))
        pp.set_thetagrids(angles)
        pp.set_theta_direction(-1)
        pp.set_theta_zero_location('N')
        plt.title('Polars: %s' % self.title)
        plt.colorbar(mappable=sm)


    def save_plot(self, filename=None, merge=False):
        if filename is None:
            filename = os.path.splitext(self._filename)[0] + '.png'
        self._plot(merge)
        plt.savefig(filename)


    def plot(self, merge=False):
        self._plot(merge)
        plt.show()


    @property
    def title(self):
        if self._title:
            return self._title
        else:
            return self._filename.split(os.sep)[-1].split('.')[0]


    @title.setter
    def title(self, value):
        self._title = value
