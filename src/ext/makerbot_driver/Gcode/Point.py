"""
A 5 dimensional Point object to be used with GcodeParser and
contained within GcodeState.  Since it is intended to only
be used with the Gcode Module, it assumes that its axes values
will only be set to integer values.  Gcode parser should only
be settings these values to ints anyway.
"""


class Point(object):

    def __init__(self):
        self.X = None
        self.Y = None
        self.Z = None
        self.A = None
        self.B = None

    def ToList(self):
        return [self.X, self.Y, self.Z, self.A, self.B]

    def SetPoint(self, codes):
        """Given a set of codes with defined values, sets this point's
        axes to those values.

        @param dict codes: The codes that may or may not contain axes values
        """
        for axis in ['X', 'Y', 'Z', 'A', 'B']:
            if axis in codes:
                setattr(self, axis, codes[axis])

    def copy(self):
        copy_point = Point()
        for axis in ['X', 'Y', 'Z', 'A', 'B']:
            setattr(copy_point, axis, getattr(self, axis))
        return copy_point
