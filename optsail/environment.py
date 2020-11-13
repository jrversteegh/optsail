"""
Environment module

Interface for providing wind / current information
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2015, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "GPL"

from datetime import datetime
from dateutil import tz

import numpy as np

from .classes import Logable


class Environment(Logable):
    def get_wind(self, positions, time=None, **kwargs):
        """Return array of wind vectors (angles, speeds) at time"""
        if time is None:
            time = datetime.now(tz=tz.tzutc())
        return self._get_wind(positions, time, **kwargs)

    def get_current(self, positions, time=None, **kwargs):
        """Return array of current vectors (angles, speeds) at time"""
        if time is None:
            time = datetime.now(tz=tz.tzutc())
        return self._get_current(positions, time, **kwargs)

    def _get_wind(self, positions, time, **kwargs):
        return np.zeros_like(positions)

    def _get_current(self, positions, time, **kwargs):
        return np.zeros_like(positions)


    def check(self):
        """Check environemnt (e.g. for updates)"""
        pass
