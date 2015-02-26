"""
An abstract preprocessor that scans lines for
certain regexs and executes certain commands
on them.
"""
from __future__ import absolute_import
import re

import makerbot_driver
from . import Processor


class LineTransformProcessor(Processor):
    """ Base implementation of a system for doing line by line
    transformations of Gcode to convert it from a non-makerbot form into
    a makerbot form of Gcode. This is used so we can simplify our
    Gcode -> s3g engine, by doing Gcode -> Gcode transforms first
    """

    def __init__(self):
        super(LineTransformProcessor, self).__init__()
        self.code_map = {}  # map {compiled_regex:replace-funcion, }

    def process_gcode(self, gcodes, gcode_info=None, callback=None):
        """ main line by line processing, inherited from Processor
        runs all code_map regex's on passed code, and saves
        replace results to return
        @param gcodes A gcode file
        @param gcode_info dict with metadata about the gcode file being processed
        @param callback for progress, expects 0-100 as percent 'done'
        @return A new gcode list post application of code_map transforms
        """
        total_bytes = float(gcode_info['size_in_bytes'])
        current_byte_count = 0

        for code in gcodes:
            tcode = self._transform_code(code)
            with self._condition:
                self.test_for_external_stop(prelocked=True)
                for code in tcode:
                    yield code
            if callback is not None:
                current_byte_count += len(code)
                percent = int(100.0 * (current_byte_count / total_bytes))
                callback(percent)

    def _transform_code(self, code):
        """ takes a single gcode, runs all transforms in code_map
        to convert it to a different style gcode. May return more (or
        fewer) lines of gcode
        @param code: a single gcode line
        @return a list of output tcodes. """
        tcode = code
        for key in self.code_map:
            match = re.match(key, code)
            if match is not None:
                tcode = self.code_map[key](match)
                break
        #Always return a list, remove '' strings
        tcode = [tcode] if not isinstance(tcode, list) else tcode
        tcode = [code for code in tcode if code is not ""]
        return tcode
