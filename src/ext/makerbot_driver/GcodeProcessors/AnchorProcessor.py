from __future__ import absolute_import
import re
import math
import contextlib

from .LineTransformProcessor import LineTransformProcessor
import makerbot_driver


class AnchorProcessor(LineTransformProcessor):
    def __init__(self):
        super(AnchorProcessor, self).__init__()
        self.is_bundleable = True
        self.code_map = {
            re.compile('[^(;]*[gG]1 [XY]-?\d'): self._transform_anchor,
        }
        self.looking_for_first_move = True
        self.speed = 1000
        self.width_over_height = .8

    def _grab_extruder(self, match):
        self.extruder = match.group(2)

    def _transform_anchor(self, match):
        return_lines = [match.string]
        if self.looking_for_first_move:
            start_position = self.get_start_position()
            return_lines = list(
                self.create_anchor_command(start_position, return_lines[0]))
            return_lines.append(match.string)
            self.looking_for_first_move = False
        return return_lines

    def create_z_move_if_necessary(self, start_movement_codes, end_movement_codes):
        """
        The platform must be moved up to the extruder to successfully anchor across the platform.
        This function checks the location of the platform, and emits the correct G1 command to 
        move the platform

        @param str start_movement_codes: Where the machine is moving from
        @param str end_movement_codes: Where the machine is moving to
        @return list: List of movements commands to move the platform
        """
        return_codes = []
        if 'Z' in start_movement_codes and 'Z' in end_movement_codes:
            start_z = start_movement_codes['Z']
            end_z = end_movement_codes['Z']
            if start_z - end_z is not 0:
                return_codes.append('G1 Z%f F%i\n' % (end_z, self.speed))
        return return_codes

    def create_anchor_command(self, start_position, end_position):
        """
        Given two G1 commands, draws an anchor between them.  Moves the platform if
        necessary

        @param str start_position: Where the machine is moving from
        @param str end_position: Where the machine is moving to
        @return list: The anchor commands
        """
        assert start_position is not None and end_position is not None
        start_movement_codes = makerbot_driver.Gcode.parse_line(
            start_position)[0] # Where the Bot is moving from
        end_movement_codes = makerbot_driver.Gcode.parse_line(end_position)[0] # Where the bot is moving to
        # Construct the next G1 command based on where the bot is moving to
        anchor_command = "G1 "
        for d in ['X', 'Y', 'Z']:
            if d in end_movement_codes:
                part = d + str(end_movement_codes[d]) # The next [XYZ] code
                anchor_command += part 
                anchor_command += ' '
        anchor_command += 'F%i ' % (self.speed)
        extruder = "E"
        extrusion_distance = self.find_extrusion_distance(
            start_movement_codes, end_movement_codes)
        anchor_command += extruder + str(extrusion_distance) + "\n"
        reset_command = "G92 %s0" % (extruder) + "\n"
        return_codes = self.create_z_move_if_necessary(start_movement_codes, end_movement_codes)
        return_codes.extend([anchor_command, reset_command])
        return return_codes

    def get_extruder(self, codes):
        extruder = 'A'
        if 'B' in codes:
            extruder = 'B'
        elif 'E' in codes:
            extruder = 'E'
        return extruder

    def find_extrusion_distance(self, start_position_codes, end_position_codes):
        layer_height = end_position_codes.get('Z', 0)
        start_position_point = []
        end_position_point = []
        for d in ['X', 'Y']:
            start_position_point.append(start_position_codes.get(d, 0))
            end_position_point.append(end_position_codes.get(d, 0))
        distance = self.calc_euclidean_distance(
            start_position_point, end_position_point)
        cross_section = self.feed_cross_section_area(
            float(layer_height), self.width_over_height)
        extrusion_distance = cross_section * distance
        return extrusion_distance

    def feed_cross_section_area(self, height, width):
        """
        Taken from MG, (hopefully not wrongfully) assumed to work
        """
        radius = height / 2.0
        tau = math.pi * 2
        return (tau / 2.0) * (radius * radius) + height * (width - height)

    def calc_euclidean_distance(self, p1, p2):
        assert len(p1) == len(p2)
        distance = 0.0
        for a, b in zip(p1, p2):
            distance += pow(a - b, 2)
        distance = math.sqrt(distance)
        return distance

    def get_start_position(self):
        start_position = (-112, -73, 150)
        if hasattr(self, 'profile') and None != self.profile:
            sp = self.profile.values['print_start_sequence']['start_position']
            start_position = (sp['start_x'], sp['start_y'], sp['start_z'])
        start_codes = "G1 X%s Y%s Z%s F3300.0 (move to waiting position)"
        start_codes = start_codes % start_position
        return start_codes
