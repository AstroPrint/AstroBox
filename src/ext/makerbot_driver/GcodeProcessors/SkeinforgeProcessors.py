"""
A set of preprocessors for the skeinforge engine
"""
from __future__ import absolute_import

import re
import warnings

from .BundleProcessor import BundleProcessor
from .LineTransformProcessor import LineTransformProcessor
from .CoordinateRemovalProcessor import CoordinateRemovalProcessor
from .RpmProcessor import RpmProcessor
from .TemperatureProcessor import GetTemperatureProcessor

import makerbot_driver


class Skeinforge50Processor(BundleProcessor):
    """
    A Processor that takes a skeinforge 50 file without start/end
    and replaces/removes deprecated commands with their replacements.
    """
    def __init__(self):
        super(Skeinforge50Processor, self).__init__()
        self.version = '12.03.14'
        self.processors = [
            CoordinateRemovalProcessor(),
            RpmProcessor(),
            SkeinforgeVersionChecker(self.version),
            GetTemperatureProcessor(),
        ]
        self.code_map = {}


class SkeinforgeVersionChecker(LineTransformProcessor):

    def __init__(self, version):
        super(SkeinforgeVersionChecker, self).__init__()
        self.is_bundleable = True
        self.version = version
        self.code_map = {
            re.compile("\(<version> (.*?) </version>\)$"): self._transform_check_version,
        }

    def _transform_check_version(self, match):
        """Scans for an expected skeinforge version number.
        @param match: a re.match (or similar) object
        """
        version_numbers = match.group(1).split('.')
        compatible_numbers = self.version.split('.')
        if not version_numbers[0] == compatible_numbers[0]:
            warnings.warn("Processing incompatible version of Skeinforge, resulting file may not be compatible with Makerbot_Driver", UserWarning)
        return match.string
