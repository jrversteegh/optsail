"""
Data module

Generic utilities for data access
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2017, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "GPL"

import os


def get_data_dir():
    try:
        return os.environ['OPTSAIL_DATA_DIR']
    except KeyError:
        return os.path.realpath(
            os.path.dirname(os.path.realpath(__file__)) + '/../../data'
        )
