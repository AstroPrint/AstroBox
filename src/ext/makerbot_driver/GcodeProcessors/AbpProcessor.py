from __future__ import absolute_import

import re

import makerbot_driver
from .LineTransformProcessor import LineTransformProcessor


class AbpProcessor(LineTransformProcessor):

    def __init__(self):
        super(AbpProcessor, self).__init__()
        self.is_bundleable = True
        self.code_map = {
            re.compile("[^;(]*[mM]106"): self._transform_m106,
            re.compile("[^;(]*[mM]107"): self._transform_m107,
        }

    def _transform_m107(self, match):
        return ""

    def _transform_m106(self, match):
        return ""
