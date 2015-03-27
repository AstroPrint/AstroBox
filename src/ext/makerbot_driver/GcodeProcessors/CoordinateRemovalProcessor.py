from __future__ import absolute_import

import re

import makerbot_driver
from .LineTransformProcessor import LineTransformProcessor


class CoordinateRemovalProcessor(LineTransformProcessor):

    """
    Remove:
    G10
    G54
    G55
    G21
    G90
    """

    def __init__(self):
        super(CoordinateRemovalProcessor, self).__init__()
        self.is_bundleable = True
        self.code_map = {
            re.compile('[^(;]*[gG]10'): self._transform_g10,
            re.compile('[^(;]*[gG]54'): self._transform_g54,
            re.compile('[^(;]*[gG]55'): self._transform_g55,
            re.compile('[^(;]*[gG]21'): self._transform_g21,
            re.compile('[^(;]*[gG]90'): self._transform_g90,
        }

    def _transform_g10(self, match):
        """
        Given a line that has an "G10" command, transforms it into
        the proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""

    def _transform_g54(self, match):
        """
        Given a line that has an "G54" command, transforms it into
        the proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""

    def _transform_g55(self, match):
        """
        Given a line that has an "G55" command, transforms it into
        the proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""

    def _transform_g21(self, match):
        """
        given a line with a G21 command, transforms it into the
        proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""

    def _transform_g90(self, match):
        """
        given a line with a G90 command, transforms it into the
        proper output.

        @param str match: The line to be transformed
        @return str: The transformed line
        """
        return ""
