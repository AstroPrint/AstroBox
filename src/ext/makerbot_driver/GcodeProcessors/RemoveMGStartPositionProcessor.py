from __future__ import absolute_import

import re
import makerbot_driver

from .LineTransformProcessor import LineTransformProcessor

class RemoveMGStartPositionProcessor(LineTransformProcessor):
    """
        This processor removes the move to start position line from a Miracle-Grue gcode file.
        This is done as of MakerWare2.2, since moving to the start position mid-dualstrusion
        print causes issues. This processor works under the assumption that the first G1
        command is the start position command

        This processor will replace the move to start position if an anchor is present
        this is done since the move to start positiion will have no bad affects
        in the presence of an anchor and it will prevent the initial movement being
        extremely slow
    """
    def __init__(self):
        super(RemoveMGStartPositionProcessor, self).__init__()
        self.code_map = {
            re.compile('^G1'): self._handle_move,
            re.compile('^G1 .*; Anchor',re.I): self._insert_start_move
        }
        self.seeking_first_move = True
        self.seeking_anchor = True
        self.start_position_move = ''

    def _handle_move(self, match):
        if self.seeking_first_move:
            self.seeking_first_move = False
            self.start_position_move = match.string           
            return []
        else:
            return [match.string]

    def _insert_start_move(self, match):
        if self.seeking_anchor:
            self.seeking_anchor = False
            return [self.start_position_move, match.string]
        else:
            return [match.string]
