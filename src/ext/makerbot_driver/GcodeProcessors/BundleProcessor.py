import re
import inspect

from .LineTransformProcessor import LineTransformProcessor
from .ProgressProcessor import ProgressProcessor


class BundleProcessor(LineTransformProcessor):

    def __init__(self):
        super(BundleProcessor, self).__init__()
        self.processors = []
        self.code_map = {}
        # Held here for testing purposes
        self._super_process_gcode = super(BundleProcessor, self).process_gcode

    def collate_codemaps(self):
        transform_code = "_transform_"
        for processor in self.processors:
            if processor.is_bundleable:
                self.code_map.update(processor.code_map)

    def process_gcode(self, gcodes, gcode_info, callback=None):

        self.collate_codemaps()

        for code in self._super_process_gcode(gcodes, gcode_info, callback):
            yield code

    def set_external_stop(self, value=True):
        super(BundleProcessor, self).set_external_stop(value)

