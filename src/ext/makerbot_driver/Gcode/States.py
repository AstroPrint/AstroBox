"""
A state machine for the gcode parser which keeps track of certain
variables.
"""
from __future__ import absolute_import

import logging

import makerbot_driver


class GcodeStates(object):
    """
    Object for storing gcoder state variables for use
    in parsing a gcode file. some gcode commands require state
    konwledge to be packetized properly.
    """
    def __init__(self):
        self._log = logging.getLogger(self.__class__.__name__)
        self.profile = None
        self.position = makerbot_driver.Gcode.Point()  # Position, In MM!!
        self.values = {}
        self.wait_for_ready_packet_delay = 100  # ms
        self.wait_for_ready_timeout = 600  # seconds
        self.percentage = 0

    def lose_position(self, axes):
        """Given a set of axes, loses the position of
        those axes.
        @param list axes: A list of axes to lose
        """
        self._log.debug(
            '{"event":"gcode_state_change", "change":"lose_position"}')
        for axis in axes:
            setattr(self.position, axis, None)

    def get_position(self):
        """Gets a usable position in steps to send to the machine
        @return list position: The current position of the machine in steps
        """
        #Check each axis first, since we need to report a bad axis if needed
        for axis in ['X', 'Y', 'Z', 'A', 'B']:
            if getattr(self.position, axis) is None:
                gcode_error = makerbot_driver.Gcode.UnspecifiedAxisLocationError()
                gcode_error.values['UnspecifiedAxis'] = axis
                raise gcode_error

        return_position = self.position.ToList()

        return return_position

    def set_build_name(self, build_name):
        if not isinstance(build_name, str):
            raise TypeError
        else:
            self._log.debug(
                '{"event":"gcode_state_change", "change":"build_name"}')
            self.values['build_name'] = build_name

    def get_axes_values(self, key):
        """
        Given a key, queries the current profile's axis list
        for the information associated with that key.  This function
        always asks the profile for information regarding the axes:
        X, Y, Z, A, B.  For compatability issues, if one of these axes is
        not present in the profile, we add a 0 for that value.

        @param string key: The information we want to get from each axis
        @return list: List of information retrieved from each axis attached to
            a profile.
        """
        axes = ['X', 'Y', 'Z', 'A', 'B']
        values = []
        for axis in axes:
            if axis in self.profile.values['axes']:
                values.append(self.profile.values['axes'][axis][key])
            else:
                values.append(0)
        return values

    def get_axes_feedrate_and_SPM(self, axes):
        """
        Given a set of axes, returns their max feedrates and
        steps per mm (SPM) values

        @param string list axes: A list of axes
        @return tuple: A tuple of feedrates and spm values.
        """
        if not isinstance(axes, list):
            raise ValueError
        feedrates = []
        spm = []
        for axis in axes:
            feedrates.append(self.profile.values['axes'][axis]['max_feedrate'])
            spm.append(self.profile.values['axes'][axis]['steps_per_mm'])
        return feedrates, spm

    @staticmethod
    def update_point_with_codes(point, codes, tool_index):
        """
        This function is static, so it can be used with non state-related
        points.

        Given a dict of codes containing axes and values, a point and
        a tool_index, sets those axes values to the state's internal 
        position's axes values. If an E codes is defined, interpolates 
        that E code's value with the correct A or B axis.

        @param Point point: Point to modify
        @param dict codes:  A dictionary that contains axes and their
            defined positions
        @param int tool_index Current tool index
        """
        if 'E' in codes:
            if 'A' in codes or 'B' in codes:
                gcode_error = makerbot_driver.Gcode.ConflictingCodesError()
                gcode_error.values['ConflictingCodes'] = ['E', 'A', 'B']
                raise gcode_error
            if tool_index is None:
                raise makerbot_driver.Gcode.NoToolIndexError
            index_map = {0: 'A', 1: 'B'}
            setattr(point, index_map[tool_index], codes['E'])
        point.SetPoint(codes)
