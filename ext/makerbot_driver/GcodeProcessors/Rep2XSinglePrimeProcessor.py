from __future__ import absolute_import

from .AnchorProcessor import AnchorProcessor
import makerbot_driver

class Rep2XSinglePrimeProcessor(AnchorProcessor):

    def __init__(self):
        super(Rep2XSinglePrimeProcessor, self).__init__()
        self.looking_for_first_move = True
        self.do_anchor = True

    def _transform_anchor(self, match):
        if "(Anchor Start)" in  match.string:
            self.do_anchor = False
        if self.looking_for_first_move:
            codes, flags, comments = makerbot_driver.Gcode.parse_line(match.string)
            prime_codes = [
                    "G1 X-105.400 Y-74.000 Z0.270 F1800.000 (Extruder Prime Start)\n",
                    "G1 X105.400 Y-74.000 Z0.270 F1800.000 E25.000 (Extruder Prime)\n",
                    "G1 X-105.400 Y-73.500 Z0.270 F1800.000 (Return)\n",
                    "G92 A0 B0 (Reset after prime)\n",
            ]
            if self.do_anchor:
                prime_codes.extend(super(Rep2XSinglePrimeProcessor, self)._transform_anchor(match))
            self.looking_for_first_move = False
            return prime_codes
        else:
            return match.string
