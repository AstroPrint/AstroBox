#Gcode parser,
from __future__ import absolute_import

import logging
import time

import makerbot_driver


class GcodeParser(object):
    """
    Read in gcode line by line, tracking some state variables and running known
    commands against an s3g machine.
    """
    def __init__(self):
        self.state = makerbot_driver.Gcode.GcodeStates()
        self.s3g = None
        self.environment = {}
        self.line_number = 1
        self._log = logging.getLogger(self.__class__.__name__)

        # Note: The datastructure looks like this:
        # [0] : command name
        # [1] : allowed codes
        # [2] : allowed flags

        self.GCODE_INSTRUCTIONS = {
            1: [self.linear_interpolation, 'XYZABEF', ''],
            4: [self.dwell, 'P', ''],
            92: [self.set_position, 'XYZABE', ''],
            130: [self.set_potentiometer_values, 'XYZAB', ''],
            161: [self.find_axes_minimums, 'F', 'XYZ'],
            162: [self.find_axes_maximums, 'F', 'XYZ'],
        }

        self.MCODE_INSTRUCTIONS = {
            18: [self.disable_axes, '', 'XYZAB'],
            70: [self.display_message, 'P', ''],
            72: [self.play_song, 'P', ''],
            73: [self.set_build_percentage, 'P', ''],
            104: [self.set_toolhead_temperature, 'ST', ''],
            109: [self.set_platform_temperature, 'ST', ''],
            126: [self.enable_extra_output, 'T', ''],
            127: [self.disable_extra_output, 'T', ''],
            132: [self.load_position, '', 'XYZAB'],
            133: [self.wait_for_tool_ready, 'PT', ''],
            134: [self.wait_for_platform_ready, 'PT', ''],
            135: [self.change_tool, 'T', ''],
            136: [self.build_start_notification, '', ''],
            137: [self.build_end_notification, '', ''],
        }

    def execute_line(self, command):
        """
        Execute a line of gcode
        @param string command Gcode command to execute
        """
        #If command is in unicode, encode it into ascii
        if isinstance(command, unicode):
            self._log.debug('{"event":"encoding_gcode_into_utf8"}')
            command = command.encode("utf8")
        elif not isinstance(command, str):
            self._log.error('{"event":"gcode_file_in_improper_format"}')
            raise makerbot_driver.Gcode.ImproperGcodeEncodingError

        try:
            command = makerbot_driver.Gcode.variable_substitute(command, self.environment)

            codes, flags, comment = makerbot_driver.Gcode.parse_line(command)

            if 'G' in codes:
                if codes['G'] in self.GCODE_INSTRUCTIONS:
                    makerbot_driver.Gcode.check_for_extraneous_codes(
                        codes.keys(), self.GCODE_INSTRUCTIONS[codes['G']][1])
                    makerbot_driver.Gcode.check_for_extraneous_codes(
                        flags, self.GCODE_INSTRUCTIONS[codes['G']][2])
                    self.GCODE_INSTRUCTIONS[codes['G']
                                            ][0](codes, flags, comment)

                else:
                    self._log.error('{"event":"unrecognized_command", "command":%s}', codes['G'])
                    gcode_error = makerbot_driver.Gcode.UnrecognizedCommandError()
                    gcode_error.values['UnrecognizedCommand'] = codes['G']
                    raise gcode_error

            elif 'M' in codes:
                if codes['M'] in self.MCODE_INSTRUCTIONS:
                    makerbot_driver.Gcode.check_for_extraneous_codes(
                        codes.keys(), self.MCODE_INSTRUCTIONS[codes['M']][1])
                    makerbot_driver.Gcode.check_for_extraneous_codes(
                        flags, self.MCODE_INSTRUCTIONS[codes['M']][2])
                    self.MCODE_INSTRUCTIONS[codes['M']
                                            ][0](codes, flags, comment)

                else:
                    self._log.error('{"event":"unrecognized_command", "command":%s}', codes['M'])
                    gcode_error = makerbot_driver.Gcode.UnrecognizedCommandError()
                    gcode_error.values['UnrecognizedCommand'] = codes['M']
                    gcode_error.values['Suggestion'] = 'This gcode command is not valid for makerbot_driver.'
                    raise gcode_error

            # Not a G or M code, should we throw here?
            else:
                if len(codes) + len(flags) > 0:
                    self._log.error('{"event":"extraneous_code"}')
                    gcode_error = makerbot_driver.Gcode.ExtraneousCodeError()
                    raise gcode_error

                else:
                    pass

        except KeyError as e:
            self._log.error(
                '{"event":"missing_code_error", "missing_code":%s}\n', e[0])
            gcode_error = makerbot_driver.Gcode.MissingCodeError()
            gcode_error.values['MissingCode'] = e[0]
            gcode_error.values['LineNumber'] = self.line_number
            gcode_error.values['Command'] = command
            gcode_error.values['Suggestion'] = 'This gcode command is not valid for makerbot_driver'
            raise gcode_error
        except makerbot_driver.Gcode.VectorLengthZeroError:
            self._log.debug('{"event":vector_length_zero_error"}')
        except makerbot_driver.Gcode.GcodeError as gcode_error:
            self._log.error('{"event":"gcode_error"}')
            gcode_error.values['Command'] = command
            gcode_error.values['LineNumber'] = self.line_number
            raise gcode_error
        self.line_number += 1

    def deprecated(self, codes, flags, comment):
        return

    def set_potentiometer_values(self, codes, flags, comment):
        """Given a set of codes, sets the machine's potentiometer value to a specified value in the codes

        @param dict codes: Codes parsed out of the gcode command
        """
        axis_codes = {
            'X': 0,
            'Y': 1,
            'Z': 2,
            'A': 3,
            'B': 4,
        }
        for axis in axis_codes.keys():
            if axis in codes:
                value = codes[axis]
                self.s3g.set_potentiometer_value(axis_codes[axis], value)

    def find_axes_maximums(self, codes, flags, command):
        """Moves the given axes in the position direction until a timeout
        or endstop is reached
        This function loses the state machine's position.
        """
        axes = makerbot_driver.Gcode.parse_out_axes(flags)
        if len(axes) == 0:
            return
        #We need some axis information to calc the DDA speed
        axes_feedrates, axes_SPM = self.state.get_axes_feedrate_and_SPM(axes)
        dda_speed = makerbot_driver.Gcode.calculate_homing_DDA_speed(
            codes['F'],
            axes_feedrates,
            axes_SPM
        )
        try:
            self.s3g.find_axes_maximums(axes, dda_speed, self.state.profile.values[
                                        'find_axis_maximum_timeout'])
        except Exception:
            raise
        else:
            self.state.lose_position(flags)

    def find_axes_minimums(self, codes, flags, comment):
        """Moves the given axes in the negative direction until a timeout
        or endstop is reached.
        This function loses the state machine's position.
        """
        axes = makerbot_driver.Gcode.parse_out_axes(flags)
        if len(axes) == 0:
            return
        #We need some axis information to calc the DDA speed
        axes_feedrates, axes_SPM = self.state.get_axes_feedrate_and_SPM(axes)
        dda_speed = makerbot_driver.Gcode.calculate_homing_DDA_speed(
            codes['F'],
            axes_feedrates,
            axes_SPM
        )
        try:
            self.s3g.find_axes_minimums(axes, dda_speed, self.state.profile.values[
                                    'find_axis_minimum_timeout'])
        except Exception:
            raise
        else:
            self.state.lose_position(flags)

    def set_position(self, codes, flags, comment):
        """Explicitely sets the position of the state machine and bot
        to the given point
        """
        new_point = self.state.position.copy()
        self.state.update_point_with_codes(new_point, codes, self.state.values.get('tool_index', None))
        new_position = new_point.ToList()
        stepped_position = makerbot_driver.Gcode.multiply_vector(
            new_position,
            self.state.get_axes_values('steps_per_mm')
        )
        try:
            self.s3g.set_extended_position(stepped_position)
        except Exception:
            raise
        else:
            self.state.update_point_with_codes(self.state.position, codes, self.state.values.get('tool_index', None))

    def wait_for_tool_ready(self, codes, flags, comment):
        """
        Waits for a toolhead for some amount of time.  If either of
        these codes are not defined (T and P respectively), the
        default values in the gcode state is used.
        """
        if 'P' in codes:
            timeout = codes['P']
        else:
            timeout = self.state.wait_for_ready_timeout
        if 'T' in codes:    
            self.state.values['last_toolhead_index'] = codes['T']
        self.s3g.wait_for_tool_ready(
            self.state.values['last_toolhead_index'],
            self.state.wait_for_ready_packet_delay,
            timeout
        )

    def wait_for_platform_ready(self, codes, flags, comment):
        """
        Waits for a platform for some amount of time.  If either
        of these codes are not defined (T and P respectively), the
        default vaules in the gcode state is used.
        """
        if 'P' in codes:
            timeout = codes['P']
        else:
            timeout = self.state.wait_for_ready_timeout
        if 'T' in codes:
            self.state.values['last_platform_index'] = codes['T']
        self.s3g.wait_for_platform_ready(
            self.state.values['last_platform_index'],
            self.state.wait_for_ready_packet_delay,
            timeout
        )

    def disable_axes(self, codes, flags, comment):
        """Disables a set of axes on the bot
        """
        self.s3g.toggle_axes(makerbot_driver.Gcode.parse_out_axes(flags), False)

    def display_message(self, codes, flags, comment):
        """Given a comment, displays a message on the bot.
        """
        row = 0  # As per the gcode protocol
        col = 0  # As per the gcode protocol
        clear_existing = False  # If false, clears the message buffer
        last_in_group = True  # If true, signifies this is the last in a group
        wait_for_button = False  # If true, signifies a button wait

        self.s3g.display_message(
            row,
            col,
            comment,
            codes['P'],
            clear_existing,
            last_in_group,
            wait_for_button,
        )

    def play_song(self, codes, flags, comment):
        """Plays a song as a certain register on the bot.
        """
        self.s3g.queue_song(codes['P'])

    def set_build_percentage(self, codes, flags, comment):
        """Sets the build percentage to a certain percentage.
        """
        percentage = codes['P']

        if percentage > 100 or percentage < 0:
            raise makerbot_driver.Gcode.BadPercentageError

        try:
            self.s3g.set_build_percent(percentage)
        except Exception:
            raise
        else:
            self.state.percentage = percentage

    def linear_interpolation(self, codes, flags, comment):
        """Movement command that has two flavors: E and AB commands.
        E Commands require a preset toolhead to use, and simply increment
        that toolhead's coordinate.
        AB Commands increment the AB axes.
        Having both E and A or B codes will throw errors.
        """
        try:
            if 'F' in codes:
                new_feedrate = codes['F']
            elif 'feedrate' in self.state.values:
                new_feedrate = self.state.values['feedrate']
            else:
                raise makerbot_driver.Gcode.NoFeedrateSpecifiedError
            if len(makerbot_driver.Gcode.parse_out_axes(codes)) > 0 or 'E' in codes:
                current_position = self.state.get_position()
                new_point = self.state.position.copy()
                self.state.update_point_with_codes(new_point, codes, self.state.values.get('tool_index', None))
                new_position = new_point.ToList()
                dda_speed = makerbot_driver.Gcode.calculate_DDA_speed(
                    current_position,
                    new_position,
                    new_feedrate,
                    self.state.get_axes_values('max_feedrate'),
                    self.state.get_axes_values('steps_per_mm'),
                )
                stepped_point = makerbot_driver.Gcode.multiply_vector(
                    new_position,
                    self.state.get_axes_values('steps_per_mm')
                )
                #Get euclidean distance for x,y,z axes
                e_distance = makerbot_driver.Gcode.Utils.calculate_euclidean_distance(current_position[:3], new_position[:3])
                #If that distance is 0, get e_distance for A axis
                if e_distance == 0:
                    e_distance = max(
                        makerbot_driver.Gcode.Utils.calculate_euclidean_distance([current_position[3]], [new_position[3]]),
                        makerbot_driver.Gcode.Utils.calculate_euclidean_distance([current_position[4]], [new_position[4]]),
                    )
                displacement_vector = makerbot_driver.Gcode.calculate_vector_difference(
                    new_position,
                    current_position,
                )
                safe_feedrate_mm_min = makerbot_driver.Gcode.get_safe_feedrate(
                    displacement_vector,
                    self.state.get_axes_values('max_feedrate'),
                    new_feedrate,
                )
                move_minutes = e_distance / safe_feedrate_mm_min
                safe_feedrate_mm_sec = safe_feedrate_mm_min / 60.0
                self.s3g.queue_extended_point(stepped_point, dda_speed, e_distance, safe_feedrate_mm_sec)

        except KeyError as e:
            if e[0] == 'feedrate':  # A key error would return 'feedrate' as the missing key,
                                 # when in respect to the executed command the 'F' command
                                 # is the one missing. So we remake the KeyError to report
                                 # 'F' instead of 'feedrate'.
                e = KeyError('F')
            raise e
        else:
            self._log.debug('{"event":"gcode_state_change", "change":"store_feedrate", "new_feedrate":%i}', new_feedrate)
            self._log.debug('{"event":"gcode_state_change", "change":"store_position", "new_position":%r}', self.state.get_position())
            self.state.values['feedrate'] = new_feedrate
            self.state.update_point_with_codes(self.state.position, codes, self.state.values.get('tool_index', None))

    def dwell(self, codes, flags, comment):
        """Pauses the machine for a specified amount of miliseconds
        Because s3g takes in microseconds, we convert miliseconds into
        microseconds and send it off.
        """
        microConstant = 1000000
        miliConstant = 1000
        d = codes['P'] * microConstant / miliConstant
        self.s3g.delay(d)

    def set_toolhead_temperature(self, codes, flags, comment):
        """Sets the toolhead temperature for a specific toolhead to
        a specific temperature.  We set the state's tool_idnex to be the
        'T' code (if present) and use that tool_index when heating.
        """
        if 'T' in codes:
            self.state.values['last_toolhead_index'] = codes['T']
        self.s3g.set_toolhead_temperature(self.state.values['last_toolhead_index'], codes['S'])

    def set_platform_temperature(self, codes, flags, comment):
        """Sets the platform temperature for a specific toolhead to a specific
        temperature.  We set the state's tool_index to be the 'T' code (if present)
        and use that tool_index when heating.
        """
        if 'T' in codes:
            self.state.values['last_platform_index'] = codes['T']
        self.s3g.set_platform_temperature(self.state.values['last_platform_index'], codes['S'])

    def load_position(self, codes, flags, comment):
        """Loads the home positions for the XYZ axes from the eeprom
        """
        axes = makerbot_driver.Gcode.parse_out_axes(flags)
        try:
            self.s3g.recall_home_positions(axes)
        except Exception:
            raise
        else:
            self.state.lose_position(axes)

    def change_tool(self, codes, flags, comments):
        """Sends a chagne tool command to the machine.
        """
        if 'T' in codes:
            self.state.values['last_toolhead_index'] = codes['T']
        self.state.values['tool_index'] = self.state.values['last_toolhead_index']
        self._log.debug('{"event":"gcode_state_change", "change":"tool_change", "new_tool_index":%i}', self.state.values['last_toolhead_index'])
        self.s3g.change_tool(self.state.values['last_toolhead_index'])

    def build_start_notification(self, codes, flags, comments):
        """Sends a build start notification command to the machine.
        """
        self._log.debug('{"event":"build_start"}')
        try:
            self.s3g.build_start_notification(self.state.values['build_name'])
        except KeyError:
            self._log.debug('{"event":"no_build_name_defined"}')
            raise makerbot_driver.Gcode.NoBuildNameError

    def build_end_notification(self, codes, flags, comments):
        """Sends a build end notification command to the machine
        """
        self._log.debug('{"event":"build_end"}')
        try:
            self.s3g.build_end_notification()
        except Exception:
            raise
        else:
            self.state.values['build_name'] = None
            self._log.debug(
                '{"event":"gcode_state_change", "change":"remove_build_name"}')
            

    def enable_extra_output(self, codes, flags, comment):
        """
        Enables an extra output attached to a certain toolhead
        of the machine
        """
        if 'T' in codes:
            self.state.values['last_extra_index'] = codes['T']
        self.s3g.toggle_extra_output(self.state.values['last_extra_index'], True)

    def disable_extra_output(self, codes, flags, comment):
        """
        Disables an extra output attached to a certain toolhead
        of the machine
        """
        if 'T' in codes:
            self.state.values['last_extra_index'] = codes['T']
        self.s3g.toggle_extra_output(self.state.values['last_extra_index'], False)
