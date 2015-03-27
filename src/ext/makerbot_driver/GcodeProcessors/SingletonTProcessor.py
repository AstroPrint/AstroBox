from __future__ import absolute_import

import re

import makerbot_driver
from .LineTransformProcessor import LineTransformProcessor


class SingletonTProcessor(LineTransformProcessor):

    def __init__(self):
        super(SingletonTProcessor, self).__init__()
        self.is_bundleable = True
        self.code_map = {
            re.compile("[^(;]*[tT]([0-9])"): self._transform_singleton
        }

    def _transform_singleton(self, match):
        return_line = 'M135 T%s\n' % (match.group(1))
        return return_line
