from __future__ import absolute_import

import re
import makerbot_driver

from .LineTransformProcessor import LineTransformProcessor

class Rep2XDualstrusionPrimeProcessor(LineTransformProcessor):

    def __init__(self):
        super(Rep2XDualstrusionPrimeProcessor, self).__init__()
        map_addendum = {
            re.compile('M135\s[tT]\d'): self._set_toolhead,
            re.compile('G1'): self._add_prime,
        }
        self.code_map.update(map_addendum)
        self.looking_for_first_move = True
        self.current_toolchange = None

    def _set_toolhead(self, match):
        self.current_toolchange = match.string
        return self.current_toolchange

    @staticmethod
    def _get_inactive_toolhead(toolchange):
        (codes, flags, comments) = makerbot_driver.Gcode.parse_line(toolchange)
        active_toolhead = codes['T']
        inactive_code_map = {0: 'B', 1: 'A'}
        return inactive_code_map[active_toolhead]

    def _get_retract_commands(self, profile, toolchange):
        inactive_toolhead = self._get_inactive_toolhead(toolchange)
        retract_commands = [
            "M135 T%i\n" % (0 if inactive_toolhead == 'A' else 1),
            "G1 %s-%i F%i\n" % (inactive_toolhead, profile.values['dualstrusion']['retract_distance_mm'], profile.values['dualstrusion']['snort_feedrate']),
            "G92 %s0\n" % (inactive_toolhead),
        ]
        return retract_commands

    def _add_prime(self, match):
        toadd = []
        if self.looking_for_first_move:
            toadd.extend([
                "M135 T0\n",
                "G1 X-105.400 Y-74.000 Z0.270 F1800.000 (Right Prime Start)\n",
                "G1 X105.400 Y-74.000 Z0.270 F1800.000 A25.000 (Right Prime)\n",
                "M135 T1\n",
                "G1 X105.400 Y-73.500 Z0.270 F1800.000 (Left Prime Start)\n",
                "G1 X-105.400 Y-73.500 Z0.270 F1800.000 B25.000 (Left Prime)\n",
                "G92 A0 B0 (Reset after prime)\n",
            ])
            if(self.profile.values['dualstrusion']['retract_distance_mm'] > 0):
                #If there is no retract there is no need to get the retract commands
                toadd.extend(self._get_retract_commands(self.profile, self.current_toolchange))
            toadd.append(self.current_toolchange)
        self.looking_for_first_move = False
        return toadd + [match.string]
