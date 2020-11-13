"""
Classes module

Generic classes
"""
__author__ = "J.R. Versteegh"
__copyright__ = "2013, Orca Software"
__contact__ = "j.r.versteegh@orca-st.com"
__version__ = "0.1"
__license__ = "GPL"

import logging
from datetime import datetime, timedelta, date, time
from dateutil.parser import parse as datetime_parse
from dateutil import tz as tzone
import six


class Object(object):
    '''Base class with generic constructor'''
    # Define slot to avoid dictionary creation
    __slots__ = []

    def __init__(self, *args, **kwargs):
        super(Object, self).__init__()



class Logable(Object):
    '''Generic class with log property'''

    def __init__(self, *args, **kwargs):
        super(Logable, self).__init__(*args, **kwargs)
        cls = self.__class__
        self._log = logging.getLogger('%s.%s' % (cls.__module__, cls.__name__))

    @property
    def log(self):
        return self._log



class OptsailError(Exception):
    pass


_datekeys = ('year', 'month', 'day')
_timekeys = ('hour', 'minute', 'second', 'microsecond', 'tzinfo')
_tzlocal = tzone.tzlocal()
_tzutc = tzone.tzutc()


class DateTime(datetime):
    """
    Extension of datetime that supports copy construction and construction from string
    """
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        """Construct immutable DateTime object

        Keyword arguments override values retrieved from args[0]

        Arguments:
        0 -- another DateTime or datetime object to copy construct from.
          -- a timedelta object indicating an offset from "now".
          -- a string value to parse the date and time from. See
             dateutil.parser for valid strings
          -- a unix timestamp
          -- "None" to indicate "now"
        0,1,2,3,4,5,6
          -- year,month,day,hour,minute,second,microsecond

        Keyword arguments:
        year    -- two or four digit year
        month   -- two or four digit year (defaults to 0)
        day     -- day of month
        hour    -- hour of the day
        minute  -- minute of the hour
        second  -- second of the minute
        microsecond -- millionths of a second
        tzinfo  -- timezone object indicating the timezone
        """

        if 'tzinfo' in kwargs:
            tz = kwargs['tzinfo']
        else:
            tz = _tzlocal

        def get_zero():
            return datetime.fromtimestamp(0, tz=tz)

        def get_now():
            return datetime.now(tz=tz)

        def has_time_key():
            for k in _timekeys:
                if k in kwargs:
                    return True
            return False

        def has_date_key():
            for k in _datekeys:
                if k in kwargs:
                    return True
            return False

        def get_init_from_args():
            if len(args) == 1:
                init = args[0]
                if init is None:
                    init = get_now()
                elif isinstance(init, six.integer_types) or isinstance(init, float):
                    init = datetime.fromtimestamp(init, tz=tz)
                elif isinstance(init, timedelta):
                    init = get_zero() + init
                elif isinstance(init, str):
                    init = datetime_parse(init)
                elif isinstance(init, time):
                    init = datetime.combine(get_now(), init)
                elif isinstance(init, date):
                    pass
                else:
                    raise OptsailError('Unexpected type of initializer for DateTime: '
                                       '%s' % type(init))
            else:
                init = datetime(*args)
            return init


        if args:
            init = get_init_from_args()
            args = ()
        else:
            if kwargs and not ('tzinfo' in kwargs and len(kwargs) == 1):
                if has_date_key():
                    init = get_now().date()
                else:
                    init = get_zero()
            else:
                # No args and no kwargs: initialize to now
                init = get_now()

        try:
            if init.tzinfo and 'tzinfo' in kwargs:
                init = init.astimezone(kwargs['tzinfo'])
        except AttributeError:
            pass

        for k in _datekeys:
            if k not in kwargs:
                kwargs[k] = getattr(init, k)
        try:
            for k in _timekeys:
                if k not in kwargs:
                    kwargs[k] = getattr(init, k)
        except AttributeError:
            pass

        # Fix a 2 digit year
        try:
            year = int(kwargs['year'])
            if year < 100:
                if year < 70:
                    year += 2000
                else:
                    year += 1900
            kwargs['year'] = year
        except KeyError:
            pass

        if 'tzinfo' not in kwargs or kwargs['tzinfo'] is None:
            kwargs['tzinfo'] = tz

        # Call datetime's constructor with appropriately setup kwargs
        return super(DateTime, cls).__new__(cls, **kwargs)


    def __str__(self):
        return self.isoformat()


    def __reduce__(self):
        """Reducer so pickling will work properly"""
        return type(self), (self.year, self.month, self.day,
                            self.hour, self.minute, self.second,
                            self.microsecond, self.tzinfo)


    def __eq__(self, other):
        return super(DateTime, self).__eq__(DateTime(other))


    def __lt__(self, other):
        return super(DateTime, self).__lt__(DateTime(other))


    def __le__(self, other):
        return super(DateTime, self).__le__(DateTime(other))


    def __gt__(self, other):
        return super(DateTime, self).__gt__(DateTime(other))


    def __ge__(self, other):
        return super(DateTime, self).__ge__(DateTime(other))


    def __ne__(self, other):
        return super(DateTime, self).__ne__(DateTime(other))


    def __add__(self, other):
        return DateTime(super(DateTime, self).__add__(other))


    def __sub__(self, other):
        s = super(DateTime, self).__sub__(other)
        return DateTime(s) if isinstance(s, date) else s


    def __round__(self, div=1):
        if isinstance(div, timedelta):
            div = div.total_seconds()
        ts = round(self.timestamp() / div) * div
        return DateTime(ts, tzinfo=self.tzinfo)


    @staticmethod
    def now(**kwargs):
        return DateTime(datetime.now(**kwargs))


    @staticmethod
    def utcnow():
        return DateTime(datetime.utcnow(), tzinfo=_tzutc)


    def dateup(self):
        d = self.date()
        if self == d:
            return d
        else:
            return (self + timedelta(days=1)).date()


    def date(self):
        return DateTime(datetime.date(self))
