"""
An interface that all future preprocessors should inherit from
"""
import os
import re
import threading

import makerbot_driver


class Processor(object):
    """ Base class for all Gcode Processors."""
    def __init__(self):
        self._external_stop = False
        # ^ set this to true from another thread to stop a processor
        self._condition = threading.Condition()
        # ^ used for all of Processor internal locking
        self.is_bundleable = False

    def process_gcode(self, gcodes, gcode_info=None, percentCallback=None):
        """ Abstract method to call gcode processing. Child functions
        MUST call 'testForExternalStop() before they exit
        @param callback is expected to be a callback that takes a int value
        0 to 100 of percent of processing complete
        """
        # Override functions MUST call test_for_external_stop(), which will
        self.test_for_external_stop()
        raise NotImplementedError("Unmplemented abstract method")

    @classmethod
    def remove_variables(cls, gcode, newvalue='0'):
        """
        removes the specified gcode variables with '0'
        gcode variables are specified as #VALUE
        @param gcode list or iterable of gcode values
        @param newvalue: replacement value, '0' if undefined
        @return a new gcode, with all variable replaced with newvalue
        """
        variable_regex = "#[^ ^\n^\r]*"
        m = re.search(variable_regex, gcode)
        while m is not None:
            gcode = gcode.replace(m.group(), newvalue)
            m = re.search(variable_regex, gcode)
        return gcode

    def set_external_stop(self, value=True):
        """ Set 'external stop' flag. If external stop is true,
        test_for_external_stop will throw anExternalStopError.
        Used to cancel/break processing loop of process_gcode.
        @param value state to set external top to,defaults to True
        """
        with self._condition:
            self._external_stop = value

    def test_for_external_stop(self, prelocked=False):
        """ If an external stop is set, this function will throw an
        ExternalStopError. This is used so a processing thread can be
        interrupted from another context if needed. Inherited implementions
        of process_gcode MUST call this function.
        @param prelocked set to True will skip locking self._condition
        """
        if not prelocked:
            with self._condition:
                if self._external_stop:
                    raise makerbot_driver.ExternalStopError
        else:  # self._condition is already locked
            if self._external_stop:
                raise makerbot_driver.ExternalStopError
        pass
