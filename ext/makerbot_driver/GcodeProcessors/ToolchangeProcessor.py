from __future__ import absolute_import

import re

import makerbot_driver
from .LineTransformProcessor import LineTransformProcessor
"""
Adds in ToolChange commands for G1 commands that switch extruders.

Currently this Processor is not Bundleable, but can be made so if necessary (which
might be necessary.
"""


class ToolchangeProcessor(LineTransformProcessor):

    def __init__(self):
        super(ToolchangeProcessor, self).__init__()
        self.is_bundleable = True
        self.extruders = {
            'A': 'M135 T0\n',
            'B': 'M135 T1\n'
        }
        self.code_map = {
            re.compile("[^;(]*([(][^)]*[)][^(;]*)*[gG]1.*?([aAbB])[.]*"): self._transform_gcode_into_toolchange,
        }
        self.current_extruder = 'A'

    def _transform_gcode_into_toolchange(self, match):
        return_lines = [match.string]
        #XOR of A in match and B in match
        if not ("A" in match.group() == "B" in match.group()):
            new_extruder = match.group(2).upper()
            if not new_extruder == self.current_extruder:
                self.current_extruder = new_extruder
                return_lines.insert(0, self.extruders[self.current_extruder])
        return return_lines
