"""
Utils module

Utility functions and decorators
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2013, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "Proprietary. All use without explicit permission forbidden"

import math
import numpy as np

_pi = math.pi
_minpi = -math.pi
_twopi = 2 * math.pi


def to_knots(value):
    return np.array(value) * (3.6 / 1.852)


def from_knots(value):
    return np.array(value) * (1.852 / 3.6)


def to_degs(value):
    return np.array(value) * (180.0 / _pi)


def from_degs(value):
    return np.array(value) * (_pi / 180.0)


def to_float(value):
    try:
        return float(value)
    except TypeError:
        result = []
        for v in value:
            try:
                result.append(float(v))
            except ValueError:
                # Conversion failed, ignore
                pass
        return np.array(result)


def norm_angle_diff(angle):
    while angle >= _pi:
        angle -= _twopi
    while angle < _minpi:
        angle += _twopi
    return angle


def norm_angle(angle):
    while angle >= _twopi:
        angle -= _twopi
    while angle < 0:
        angle += _twopi
    return angle


def angle_diff(angle1, angle2):
    return norm_angle_diff(angle1 - angle2)
