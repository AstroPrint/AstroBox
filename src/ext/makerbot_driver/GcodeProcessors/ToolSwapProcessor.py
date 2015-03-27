from __future__ import absolute_import

import re

from .LineTransformProcessor import LineTransformProcessor
import makerbot_driver


class ToolSwapProcessor(LineTransformProcessor):
    """
    A ToolSwapProcessor meant to be run on a gcode file compatible
    with makerbot_driver
    """

    def __init__(self):
        super(ToolSwapProcessor, self).__init__()
        self.is_bundleable = True
        self.code_map = {
            re.compile("[^(;]*([aAbB])|[^(;]*[tT]([0-9])"): self._transform_tool_swap,
        }

    def _transform_tool_swap(self, match):
        line = match.string
        line = line.upper()
        holder = '%'
        line = line.replace('A', holder)
        line = line.replace('B', 'A')
        line = line.replace(holder, 'B')
        line = line.replace('T0', holder)
        line = line.replace('T1', 'T0')
        line = line.replace(holder, 'T1')
        return line
