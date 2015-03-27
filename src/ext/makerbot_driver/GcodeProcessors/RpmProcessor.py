"""
A preprocessor that will remove all
RPM commands from a gcode file.

Removals:

M101
M102
M103
M108
"""
from __future__ import absolute_import

import re

import makerbot_driver
from .LineTransformProcessor import LineTransformProcessor


class RpmProcessor(LineTransformProcessor):

    def __init__(self):
        super(RpmProcessor, self).__init__()
        self.is_bundleable = True
        self.code_map = {
            re.compile('[^(;]*[mM]101'): self._transform_m101,
            re.compile('[^(;]*[mM]102'): self._transform_m102,
            re.compile('[^(;]*[mM]103'): self._transform_m103,
            re.compile('[^(;]*[mM]108'): self._transform_m108,
        }

    def _transform_m101(self, match):
        """
        Given a line that has an "M101" command, transforms it into
        the proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""

    def _transform_m102(self, match):
        """
        Given a line that has an "M102" command, transforms it into
        the proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""

    def _transform_m103(self, match):
        """
        Given a line that has an "M103" command, transforms it into
        the proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""

    def _transform_m108(self, match):
        """
        Given a line that has an "M108" command, transforms it into
        the proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        codes, flags, comments = makerbot_driver.Gcode.parse_line(match.string)
        #Since were using variable_replace in gcode.utils, we need to make the codes dict
        #a dictionary of only strings
        string_codes = {}
        for key in codes:
            string_codes[str(key)] = str(codes[key])
        if 'T' not in codes:
            transformed_line = ''
        else:
            transformed_line = 'M135 T#T'  # Set the line up for variable replacement
            transformed_line = makerbot_driver.Gcode.variable_substitute(transformed_line, string_codes)
            if comments != '':
                for char in ['\n', '\r']:
                    comments = comments.replace(char, '')
                transformed_line += '; ' + comments
            transformed_line += '\n'
        return transformed_line
