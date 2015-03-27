from __future__ import absolute_import

import re

import makerbot_driver
from .LineTransformProcessor import LineTransformProcessor


class RemoveProgressProcessor(LineTransformProcessor):

    def __init__(self):
        super(RemoveProgressProcessor, self).__init__()
        self.is_bundleable = True
        self.code_map = {
            re.compile("[^;(]*[mM]73"): self._transform_m73,
            re.compile("[^;(]*[mM]136"): self._transform_m136,
            re.compile("[^;(]*[mM]137"): self._transform_m137,
        }

    def _transform_m73(self, match):
        return ""

    def _transform_m137(self, match):
        return ""

    def _transform_m136(self, match):
        return ""
