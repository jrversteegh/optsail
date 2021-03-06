"""
Performance module

Boat performance class
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2016, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "GPL"

import numpy as np

from .classes import Object
from .polars import Polars


class Performance(Object):

    def __init__(self, *args, **kwargs):
        super(Performance, self).__init__(*args, **kwargs)
        try:
            self._polars = kwargs['polars']
        except KeyError:
            self._polars = [Polars()]


    def get(self, angles, wind_speed=None, squeeze=True):
        speeds = [polar.get(angles, wind_speed, squeeze) for polar in self._polars]
        max_speed = np.amax(speeds, axis=0)
        max_i = np.argmax(speeds, axis=0)
        return (max_speed, max_i)


    def get_optimal_ranges(self, wind_speeds):
        wind = zip(*[polar.get_optimal_ranges(wind_speeds) for polar in self._polars])
        upwind = np.array(wind[0])
        downwind = np.array(wind[1])
        vmgui = np.argmax(upwind[:, 1], axis=0)
        vmgdi = np.argmin(downwind[:, 1], axis=0)
        return (
            np.vstack((upwind[vmgui][0], vmgui)),
            np.vstack((downwind[vmgdi][0], vmgdi)),
        )
