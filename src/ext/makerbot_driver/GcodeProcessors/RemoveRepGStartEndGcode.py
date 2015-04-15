from __future__ import absolute_import

import makerbot_driver
from .Processor import Processor


class RemoveRepGStartEndGcode(Processor):

    def process_gcode(self, gcodes, gcode_info, callback=None):
        startgcode = False
        endgcode = False
        total_bytes = float(gcode_info['size_in_bytes'])
        current_byte_count = 0

        for code in gcodes:
            if startgcode:
                if(self.get_comment_match(code, 'end of start.gcode')):
                    startgcode = False
            elif endgcode:
                if(self.get_comment_match(code, 'end End.gcode')):
                    endgcode = False
            else:
                if (self.get_comment_match(code, '**** start.gcode')):
                    startgcode = True
                elif (self.get_comment_match(code, '**** End.gcode')):
                    endgcode = True
                else:
                    with self._condition:
                            if self._external_stop:
                                    raise makerbot_driver.ExternalStopError
                            yield code
                current_byte_count += len(code)
                if callback is not None:
                    percent = int(100.0 * (current_byte_count / total_bytes))
                    callback(percent)

    def get_comment_match(self, gcode, match):
        (codes, flags, comments) = makerbot_driver.Gcode.parse_line(gcode)
        axis = None
        if comments.find(match) is -1:
            return False
        else:
            return True
