from __future__ import absolute_import

# Some utilities for speaking s3g
import struct
import array
import time
import serial

import makerbot_driver
import uuid


class s3g(object):
    """ Represents an interface to a s3g driven bot. Contains methods and functions to
    read and write data to the bot.  No data is cached by this driver, all data is requested
    over the USB bus when queried.
    """

    POINT_LENGTH = 3
    EXTENDED_POINT_LENGTH = 5

    @classmethod
    def from_filename(cls, port, condition, baudrate=115200, timeout=.2):
        """Constructs and returns an s3g object connected to the
        passed file endpoint passed as a string @port (ie 'COM0' or '/dev/tty9')

        @param port target Serial port name
        @param baurdate baudrace 115200 assumed
        @param timeout, time allowance before timeout error. 0.2 assummed
        @return s3g object, equipped with a StreamWrtier directed at port.
        """
        s = serial.Serial(port, baudrate=baudrate, timeout=timeout)

        # begin baud rate hack
        #
        # There is an interaction between the 8U2 firmware and PySerial where
        # PySerial thinks the 8U2 is already running at the specified baud rate and
        # it doesn't actually issue the ioctl calls to set the baud rate. We work
        # around it by setting the baud rate twice, to two different values. This
        # forces PySerial to issue the correct ioctl calls.
        s.baudrate = 9600
        s.baudrate = baudrate
        # end baud rate hack

        mb_streamWriter = makerbot_driver.Writer.StreamWriter(s, condition)
        return s3g(mb_streamWriter)

    def __init__(self, mb_stream_writer=None):
        self.writer = mb_stream_writer
        self._eeprom_reader = None
        self.print_to_file_type = 's3g'
        self.tool_query_code = 'Bbb'

    def set_print_to_file_type(self, print_to_file_type):
        self.print_to_file_type = print_to_file_type

    def init_eeprom_reader(self, firmware_version=None):
            self._eeprom_reader = makerbot_driver.EEPROM.EepromReader.factory(
                self, firmware_version)

    @property
    def eeprom_reader(self):
        if self._eeprom_reader is None:
            self._eeprom_reader = makerbot_driver.EEPROM.EepromReader.factory(
                self)
        return self._eeprom_reader

    def close(self):
        """ If any ports are open for this s3g bot, it closes those ports """
        if self.writer:
            self.writer.close()

    def is_open(self):
        """@returns true if we have a writer and it is open. False otherwise."""
        if self.writer:
            return self.writer.is_open()
        return False

    def open(self):
        """ If a writer with data exists in this bot, attempts to open that writer."""
        if self.writer:
            self.writer.open()

    def get_version(self):
        """
        Get the firmware version number of the connected machine
        @return Version number
        """
        payload = struct.pack(
            '<BH',
            makerbot_driver.host_query_command_dict['GET_VERSION'],
            makerbot_driver.s3g_version,
        )

        response = self.writer.send_query_payload(payload)
        [response_code, version] = makerbot_driver.Encoder.unpack_response(
            '<BH', response)
        return version

    def get_name(self):
        """
        Get stored Bot Name
        @return a string for the name
        TODO: merge this function with future eeprom read/write module
        """
        name = self.eeprom_reader.read_data('MACHINE_NAME')
        return name[0]

    def get_toolhead_count(self):
        """
        @return the toolhead count of this bot
        """
        data = self.eeprom_reader.read_data('TOOL_COUNT')
        return data[0]

    def get_vid_pid(self):
        """
        Due to a production issue with a vendor, we do not
        trust the VID/PID in all EEPROMS, and the generic
        get_vid_pid most used should return the interface VID/PID,
        not the eeprom vid_pid. """
        return self.get_vid_pid_iface()

    def get_vid_pid_eeprom(self):
        """
        @returns tuple of vid,pid. tuple from EEPROM (None,None) on error
        """
        reader = self.create_reader()
        data = reader.read_data('VID_PID_INFO')
        return data[0], data[1]

    def get_vid_pid_iface(self):
        """
        Reads VID/PID values from the serial port object associated
        with this device.
        @return USB vid/pid tuple from the usb chip on the machine,
        """
        vid = None
        pid = None
        if self.writer is not None:
            if isinstance(self.writer, makerbot_driver.Writer.StreamWriter):
                portname = self.writer.file.port
                detector = makerbot_driver.get_gMachineDetector()
                vid, pid = detector.vid_pid_from_portname(portname)
        return vid, pid

    def get_verified_status(self, verified_pid=makerbot_driver.vid_pid[1]):
        """
        @returns true if this firmware is marked as verified
        """
        vid_pid = self.get_vid_pid()
        return vid_pid[1] is verified_pid

    def get_advanced_version(self):
        """
        Get the firmware version number of the connected machine
        @return Version number
        """
        payload = struct.pack(
            '<BH',
            makerbot_driver.host_query_command_dict['GET_ADVANCED_VERSION'],
            makerbot_driver.s3g_version,
        )

        response = self.writer.send_query_payload(payload)
        [response_code,
         version,
         internal_version,
         software_variant,
         reserved_a,
         reserved_b] = makerbot_driver.Encoder.unpack_response('<BHHBBH', response)

        version_info = {
            'Version': version,
            'InternalVersion': internal_version,
            'SoftwareVariant': software_variant,
            'ReservedA': reserved_a,
            'ReservedB': reserved_b,
        }

        return version_info

    def capture_to_file(self, filename):
        """
        Capture all subsequent commands up to the 'end capture' command to a file with the given filename on an SD card.
        @param str filename: The name of the file to write to on the SD card
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['CAPTURE_TO_FILE'],
        )
        payload += filename
        payload += '\x00'

        response = self.writer.send_query_payload(payload)

        [response_code, sd_response_code] = makerbot_driver.Encoder.unpack_response('<BB', response)
        if sd_response_code != makerbot_driver.sd_error_dict['SUCCESS']:
            raise makerbot_driver.SDCardError(sd_response_code)

    def end_capture_to_file(self):
        """
        Send the end capture signal to the bot, so it stops capturing data and writes all commands out to a file on the SD card
        @return The number of bytes written to file
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['END_CAPTURE'],
        )

        response = self.writer.send_query_payload(payload)

        [response_code, sdResponse] = makerbot_driver.Encoder.unpack_response(
            '<BI', response)
        return sdResponse

    def reset(self):
        """
        reset the bot, unless the bot is waiting to tell us a build is cancelled.
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['RESET'],
        )

        self.writer.send_action_payload(payload)

    def is_finished(self):
        """
        Checks if the steppers are still executing a command
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['IS_FINISHED'],
        )

        response = self.writer.send_query_payload(payload)

        [response_code, isFinished] = makerbot_driver.Encoder.unpack_response(
            '<B?', response)
        return isFinished

    def clear_buffer(self):
        """
        Clears the buffer of all commands
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['CLEAR_BUFFER'],
        )

        self.writer.send_action_payload(payload)

    def pause(self):
        """
        pause the machine
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['PAUSE'],
        )

        self.writer.send_action_payload(payload)

    def get_build_stats(self):
        """
        Get some statistics about the print currently running, or the last print if no print is active
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['GET_BUILD_STATS'],
        )

        response = self.writer.send_query_payload(payload)

        [response_code,
         build_state,
         build_hours,
         build_minutes,
         line_number,
         reserved] = makerbot_driver.Encoder.unpack_response('<BBBBLL', response)

        info = {
            'BuildState': build_state,
            'BuildHours': build_hours,
            'BuildMinutes': build_minutes,
            'LineNumber': line_number,
            'Reserved': reserved
        }
        return info

    def get_communication_stats(self):
        """
        Get some communication statistics about traffic on the tool network from the Host.
        @return a dictionary of communication stats, keyed by stat name
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['GET_COMMUNICATION_STATS'],
        )

        response = self.writer.send_query_payload(payload)

        [response_code,
         packetsReceived,
         packetsSent,
         nonResponsivePacketsSent,
         packetRetries,
         noiseBytes] = makerbot_driver.Encoder.unpack_response('<BLLLLL', response)

        info = {
            'PacketsReceived': packetsReceived,
            'PacketsSent': packetsSent,
            'NonResponsivePacketsSent': nonResponsivePacketsSent,
            'PacketRetries': packetRetries,
            'NoiseBytes': noiseBytes,
        }
        return info

    def get_motherboard_status(self):
        """
        Retrieve bits of information about the motherboard
        POWER_ERROR : An error was detected with the system power.
        HEAT_SHUTDOWN : The heaters were shutdown because the bot was inactive for over 20 minutes
        @return: A python dictionary of various flags and whether they were set or not at reset
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['GET_MOTHERBOARD_STATUS'],
        )

        response = self.writer.send_query_payload(payload)

        [response_code, bitfield] = makerbot_driver.Encoder.unpack_response(
            '<BB', response)

        bitfield = makerbot_driver.Encoder.decode_bitfield(bitfield)
        flags = {
            'preheat': bitfield[0],
            'manual_mode': bitfield[1],
            'onboard_script': bitfield[2],
            'onboard_process': bitfield[3],
            'wait_for_button': bitfield[4],
            'build_cancelling': bitfield[5],
            'heat_shutdown': bitfield[6],
            'power_error': bitfield[7],
        }
        return flags

    def extended_stop(self, halt_steppers, clear_buffer):
        """
        Stop the stepper motor motion and/or reset the command buffer.  This differs from the
        reset and abort commands in that a soft reset of all functions isnt called.
        @param boolean halt_steppers: A flag that if true will stop the steppers
        @param boolean clear_buffer: A flag that, if true, will clear the buffer
        """
        bitfield = 0
        if halt_steppers:
            bitfield |= 0x01
        if clear_buffer:
            bitfield |= 0x02

        payload = struct.pack(
            '<Bb',
            makerbot_driver.host_query_command_dict['EXTENDED_STOP'],
            bitfield,
        )

        response = self.writer.send_query_payload(payload)

        [response_code, extended_stop_response] = makerbot_driver.Encoder.unpack_response('<BB', response)

        if extended_stop_response != 0:
            raise makerbot_driver.ExtendedStopError

    def wait_for_platform_ready(self, tool_index, delay, timeout):
        """
        Halts the machine until the specified toolhead reaches a ready state, or if the
        timeout is reached.  Toolhead is ready if its temperature is within a specified
        range.
        @param int tool_index: toolhead index
        @param int delay: Time in ms between packets to query the toolhead
        @param int timeout: Time to wait in seconds for the toolhead to heat up before moving on
        """
        payload = struct.pack(
            '<BBHH',
            makerbot_driver.host_action_command_dict[
                'WAIT_FOR_PLATFORM_READY'],
            tool_index,
            delay,
            timeout
        )

        self.writer.send_action_payload(payload)

    def wait_for_tool_ready(self, tool_index, delay, timeout):
        """
        Halts the machine until the specified toolhead reaches a ready state, or if the
        timeout is reached.  Toolhead is ready if its temperature is within a specified
        range.
        @param int tool_index: toolhead index
        @param int delay: Time in ms between packets to query the toolhead
        @param int timeout: Time to wait in seconds for the toolhead to heat up before moving on
        """
        payload = struct.pack(
            '<BBHH',
            makerbot_driver.host_action_command_dict['WAIT_FOR_TOOL_READY'],
            tool_index,
            delay,
            timeout
        )

        self.writer.send_action_payload(payload)

    def delay(self, delay):
        """
        Halts all motion for the specified amount of time
        @param int delay: delay time, in microseconds
        """
        payload = struct.pack(
            '<BI',
            makerbot_driver.host_action_command_dict['DELAY'],
            delay
        )

        self.writer.send_action_payload(payload)

    def change_tool(self, tool_index):
        """
        Change to the specified toolhead
        @param int tool_index: toolhead index
        """
        payload = struct.pack(
            '<BB',
            makerbot_driver.host_action_command_dict['CHANGE_TOOL'],
            tool_index
        )

        self.writer.send_action_payload(payload)

    def toggle_axes(self, axes, enable):
        """
        Used to explicitly power steppers on or off.
        @param list axes: Array of axis names ['x', 'y', ...] to configure
        @param boolean enable: If true, enable all selected axes. Otherwise, disable the selected
               axes.
        """
        axes_bitfield = makerbot_driver.Encoder.encode_axes(axes)
        if enable:
            axes_bitfield |= 0x80

        payload = struct.pack(
            '<BB',
            makerbot_driver.host_action_command_dict['ENABLE_AXES'],
            axes_bitfield
        )

        self.writer.send_action_payload(payload)

    def queue_extended_point_new(self, position, duration, relative_axes):
        """
        Queue a position with the new style!  Moves to a certain position over a given duration
        with either relative or absolute positioning.  Relative vs. Absolute positioning
        is done on an axis to axis basis.

        @param list position: A 5 dimentional position in steps specifying where each axis should move to
        @param int duration: The total duration of the move in miliseconds
        @param list relative_axes: Array of axes whose coordinates should be considered relative
        """
        if len(position) != s3g.EXTENDED_POINT_LENGTH:
            raise makerbot_driver.PointLengthError(len(position))

        payload = struct.pack(
            '<BiiiiiIB',
            makerbot_driver.host_action_command_dict[
                'QUEUE_EXTENDED_POINT_NEW'],
            position[0], position[1], position[2], position[3], position[4],
            duration,
            makerbot_driver.Encoder.encode_axes(relative_axes)
        )

        self.writer.send_action_payload(payload)

    def store_home_positions(self, axes):
        """
        Write the current axes locations to the EEPROM as the home position
        @param list axes: Array of axis names ['x', 'y', ...] whose position should be saved
        """
        payload = struct.pack(
            '<BB',
            makerbot_driver.host_action_command_dict['STORE_HOME_POSITIONS'],
            makerbot_driver.Encoder.encode_axes(axes)
        )

        self.writer.send_action_payload(payload)

    def set_potentiometer_value(self, axis, value):
        """
        Sets the value of the digital potentiometers that control the voltage references for the botsteps
        @param axis: Axis whose potentiometers should be set.  Each axis has a specific code:
            X: 0,
            Y: 1,
            Z: 2,
            A: 3,
            B: 4,
        @param int value: The value to set the digital potentiometer to.
        """
        max_value = 127
        value = min(value, max_value)
        payload = struct.pack(
            '<BBB',
            makerbot_driver.host_action_command_dict['SET_POT_VALUE'],
            axis,
            value,
        )

        self.writer.send_action_payload(payload)

    def set_beep(self, frequency, duration):
        """
        Play a tone of the specified frequency for the specified duration.
        @param int frequency: Frequency of the tone, in hz
        @param int duration: Duration of the tone, in ms
        """
        payload = struct.pack(
            '<BHHB',
            makerbot_driver.host_action_command_dict['SET_BEEP'],
            frequency,
            duration,
            0x00
        )

        self.writer.send_action_payload(payload)

    def set_RGB_LED(self, r, g, b, blink):
        """
        Set the brightness and blink rate for RBG LEDs
        @param int r: The r value (0-255) for the LEDs
        @param int g: The g value (0-255) for the LEDs
        @param int b: The b value (0-255) for the LEDs
        @param int blink: The blink rate (0-255) for the LEDs
        """
        payload = struct.pack(
            '<BBBBBB',
            makerbot_driver.host_action_command_dict['SET_RGB_LED'],
            r,
            g,
            b,
            blink,
            0x00
        )

        self.writer.send_action_payload(payload)

    def recall_home_positions(self, axes):
        """
        Recall and move to the home positions written to the EEPROM
        @param axes: Array of axis names ['x', 'y', ...] whose position should be saved
        """
        payload = struct.pack(
            '<BB',
            makerbot_driver.host_action_command_dict['RECALL_HOME_POSITIONS'],
            makerbot_driver.Encoder.encode_axes(axes)
        )

        self.writer.send_action_payload(payload)

    def init(self):
        """
        Sends 'init' packet to machine to Initialize the machine to a default state
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['INIT']
        )

        self.writer.send_action_payload(payload)

    def tool_query(self, tool_index, command, tool_payload=None):
        """
        Query a toolhead for some information
        @param int tool_index: toolhead index
        @param int command: command to send to the toolhead
        @param bytearray tool_payload: payload that goes along with the command, or None
               if the command does not have a payload
        @return bytearray payload: received from the tool
        """
        if tool_index > makerbot_driver.max_tool_index or tool_index < 0:
            raise makerbot_driver.ToolIndexError(1)

        payload = struct.pack(
            '<%s' % self.tool_query_code,
            makerbot_driver.host_query_command_dict['TOOL_QUERY'],
            tool_index,
            command,
        )

        if tool_payload is not None:
            payload += tool_payload

        return self.writer.send_query_payload(payload)

    def read_named_value_from_EEPROM(self, name=None, context=None):
        return self.eeprom_reader.read_data(name, context)

    def read_from_EEPROM(self, offset, length):
        """
        Read some data from the machine. The data structure is implementation specific.
        @param byte offset: EEPROM location to begin reading from
        @param int length: Number of bytes to read from the EEPROM (max 31)
        @return byte array of data read from EEPROM
        """
        # We can only read 31 bytes
        if length > makerbot_driver.maximum_payload_length - 1:
            raise makerbot_driver.EEPROMLengthError(length)

        payload = struct.pack(
            '<BHb',
            makerbot_driver.host_query_command_dict['READ_FROM_EEPROM'],
            offset,
            length
        )

        response = self.writer.send_query_payload(payload)

        return response[1:]

    def write_to_EEPROM(self, offset, data):
        """
        Write some data to the machine. The data structure is implementation specific.
        @param byte offset: EEPROM location to begin writing to
        @param int data: Data to write to the EEPROM
        """
        code = '<Bhb'
        # Check the length of data against maximum_payload_length and the compulsory packet values
        if len(data) > makerbot_driver.maximum_payload_length - struct.calcsize(code):
            raise makerbot_driver.EEPROMLengthError(len(data))

        payload = struct.pack(
            code,
            makerbot_driver.host_query_command_dict['WRITE_TO_EEPROM'],
            offset,
            len(data),
        )

        payload += data

        response = self.writer.send_query_payload(payload)

        if response[1] != len(data):
            raise makerbot_driver.EEPROMMismatchError(response[1])

    def get_available_buffer_size(self):
        """
        Gets the available buffer size
        @return Available buffer size, in bytes
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict[
                'GET_AVAILABLE_BUFFER_SIZE'],
        )

        response = self.writer.send_query_payload(payload)
        [response_code, buffer_size] = makerbot_driver.Encoder.unpack_response(
            '<BI', response)

        return buffer_size

    def abort_immediately(self):
        """
        Stop the machine by disabling steppers, clearing the command buffers, and
        instructing the toolheads to shut down
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['ABORT_IMMEDIATELY']
        )

        resposne = self.writer.send_query_payload(payload)

    def playback_capture(self, filename):
        """
        Instruct the machine to play back (build) a file from it's SD card.
        @param str filename: Name of the file to print. Should have been retrieved by
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['PLAYBACK_CAPTURE'],
        )

        payload += filename
        payload += '\x00'

        response = self.writer.send_query_payload(payload)

        [response_code, sd_response_code] = makerbot_driver.Encoder.unpack_response('<BB', response)

        if sd_response_code != makerbot_driver.sd_error_dict['SUCCESS']:
            raise makerbot_driver.SDCardError(sd_response_code)

    def get_next_filename(self, reset):
        """
        Gets the 'next' filename on the SD card if an SD card is inserted into the 'bot
        @param boolean reset: If true, reset the file index to zero and return the first  available filename.
        @return the next filename on the machine, as a string.
        """
        flag = 1 if reset else 0

        payload = struct.pack(
            '<Bb',
            makerbot_driver.host_query_command_dict['GET_NEXT_FILENAME'],
            flag,
        )
        response = self.writer.send_query_payload(payload)
        [response_code, sd_response_code, filename] = makerbot_driver.Encoder.unpack_response_with_string('<BB', response)

        if sd_response_code != makerbot_driver.sd_error_dict['SUCCESS']:
            raise makerbot_driver.SDCardError(sd_response_code)

        return filename

    def get_build_name(self):
        """
        Get the build name of the file printing on the machine, if any.
        @param str filename: The filename of the current print
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['GET_BUILD_NAME']
        )

        response = self.writer.send_query_payload(payload)
        [response_code, filename] = makerbot_driver.Encoder.unpack_response_with_string('<B', response)

        return filename

    def get_extended_position(self):
        """
        Gets the current machine position
        @return tuple position: containing the current 5D position (x,y,z,a,b) location and endstop states.
        """
        payload = struct.pack(
            '<B',
            makerbot_driver.host_query_command_dict['GET_EXTENDED_POSITION'],
        )

        response = self.writer.send_query_payload(payload)

        [response_code,
         x, y, z, a, b,
         endstop_states] = makerbot_driver.Encoder.unpack_response('<BiiiiiH', response)

        return [x, y, z, a, b], endstop_states

    def find_axes_minimums(self, axes, rate, timeout):
        """
        Move the toolhead in the negativedirection, along the specified axes,
        until an endstop is reached or a timeout occurs.
        @param list axes: Array of axis names ['x', 'y', ...] to move
        @param double rate: Movement rate, in steps/??
        @param double timeout: Amount of time in seconds to move before halting the command
        """
        payload = struct.pack(
            '<BBIH',
            makerbot_driver.host_action_command_dict['FIND_AXES_MINIMUMS'],
            makerbot_driver.Encoder.encode_axes(axes),
            rate,
            timeout
        )

        self.writer.send_action_payload(payload)

    def find_axes_maximums(self, axes, rate, timeout):
        """
        Move the toolhead in the positive direction, along the specified axes,
        until an endstop is reached or a timeout occurs.
        @param list axes: Array of axis names ['x', 'y', ...] to move
        @param double rate: Movement rate, in steps/??
        @param double timeout: Amount of time to move in seconds before halting the command
        """
        payload = struct.pack(
            '<BBIH',
            makerbot_driver.host_action_command_dict['FIND_AXES_MAXIMUMS'],
            makerbot_driver.Encoder.encode_axes(axes),
            rate,
            timeout
        )

        self.writer.send_action_payload(payload)

    def tool_action_command(self, tool_index, command, tool_payload=''):
        """
        Send a command to a toolhead
        @param int tool_index: toolhead index
        @param int command: command to send to the toolhead
        @param bytearray tool_payload: payload that goes along with the command
        """
        if tool_index > makerbot_driver.max_tool_index or tool_index < 0:
            raise makerbot_driver.ToolIndexError(tool_index)

        payload = struct.pack(
            '<BBBB',
            makerbot_driver.host_action_command_dict['TOOL_ACTION_COMMAND'],
            tool_index, command, len(tool_payload)
        )

        if tool_payload != '':
            payload += tool_payload

        self.writer.send_action_payload(payload)

    def queue_extended_point_x3g(self, position, dda_rate, relative_axes, distance, feedrate):
        """
        Queue a position with the x3g style!  Moves to a certain position over a given duration
        with either relative or absolute positioning.  Relative vs. Absolute positioning
        is done on an axis to axis basis.
        @param list position: A 5 dimentional position in steps specifying where each axis should move to
        @param int dda_rate: Steps per second along the master axis
        @param list relative_axes: Array of axes whose coordinates should be considered relative
        @param float distance: distance in millimeters moved in (x,y,z) space OR if distance(x,y,z) == 0, then max(distance(A),distance(B))
        @param float feedrate: the actual feedrate in units of millimeters/second
        """
        if len(position) != s3g.EXTENDED_POINT_LENGTH:
            raise makerbot_driver.PointLengthError(len(position))

        payload = struct.pack(
            '<BiiiiiIBfh',
        makerbot_driver.makerbot_driver.host_action_command_dict[
            'QUEUE_EXTENDED_POINT_ACCELERATED'],
        position[0], position[1], position[2], position[3], position[4],
        dda_rate,
        makerbot_driver.Encoder.encode_axes(relative_axes),
        float(distance),
        int(feedrate * 64.0)
        )
        self.writer.send_action_payload(payload)

    def queue_extended_point(self, position, dda_speed, e_distance, feedrate_mm_sec, relative_axes=[]):
        """
        Queue a position: this function chooses the correct movement command based on the print_to_file_type
        Moves to a certain position over a given duration with either relative or absolute positioning. 
        Relative vs. Absolute positioning is done on an axis to axis basis.
        @param list position: A 5 dimentional position in steps specifying where each axis should move to
        @param int dda_speed: microseconds per step
        @param float e_distance: distance in millimeters moved in (x,y,z) space OR if distance(x,y,z) == 0, then max(distance(A),distance(B))
        @param float feedrate_mm_sec: the actual feedrate in units of millimeters/second
        @param list relative_axes: Array of axes whose coordinates should be considered relative
        """
    
        if len(position) != s3g.EXTENDED_POINT_LENGTH:
            raise makerbot_driver.PointLengthError(len(position))

        if self.print_to_file_type == 'x3g' : 
            dda_rate = 1000000.0 / float(dda_speed)
            self.queue_extended_point_x3g(position, dda_rate, relative_axes,
                      e_distance, feedrate_mm_sec)
        else:
            self.queue_extended_point_classic(position, dda_speed)

    def queue_extended_point_classic(self, position, dda_speed):
        """
        Queue a position with the classic style!  Moves to a certain position over a given duration
        with either relative or absolute positioning.  Relative vs. Absolute positioning
        is done on an axis to axis basis.
        @param list position: A 5 dimentional position in steps specifying where each axis should move to
        @param int dda_speed: microseconds per step
        """
        if len(position) != s3g.EXTENDED_POINT_LENGTH:
            raise makerbot_driver.PointLengthError(len(position))

        payload = struct.pack(
            '<BiiiiiI',
        makerbot_driver.host_action_command_dict[
            'QUEUE_EXTENDED_POINT'],
        position[0], position[1], position[2],
        position[3], position[4], dda_speed
        )

        self.writer.send_action_payload(payload)

    def set_extended_position(self, position):
        """
        Inform the machine that it should consider this point its current point
        @param list position: 5D position to set the machine to, in steps.
        """
        if len(position) != s3g.EXTENDED_POINT_LENGTH:
            raise makerbot_driver.PointLengthError(len(position))

        payload = struct.pack(
            '<Biiiii',
            makerbot_driver.host_action_command_dict['SET_EXTENDED_POSITION'],
            position[0], position[1], position[2],
            position[3], position[4],
        )

        self.writer.send_action_payload(payload)

    def wait_for_button(self, button, timeout, ready_on_timeout, reset_on_timeout, clear_screen):
        """
        Wait until a user either presses a button on the interface board, or a timeout occurs
        @param str button: A button, must be one of the following: up, down, left, right center.
        @param double timeout: Duration, in seconds, the bot will wait for a response.
          A timeout of 0 indicated no timeout.  TimeoutReadyState, timeoutReset determine what
          action is taken after timeout
        @param boolean ready_on_timeout: Bot changes to the ready state after tiemout
        @param boolean reset_on_timeout: Resets the bot on timeout
        @param boolean clear_screen: Clears the screen on button press
        """
        if button == 'center':
            button = 0x01
        elif button == 'right':
            button = 0x02
        elif button == 'left':
            button = 0x04
        elif button == 'down':
            button = 0x08
        elif button == 'up':
            button = 0x10
        else:
            raise makerbot_driver.ButtonError(button)

        optionsField = 0
        if ready_on_timeout:
            optionsField |= 0x01
        if reset_on_timeout:
            optionsField |= 0x02
        if clear_screen:
            optionsField |= 0x04

        payload = struct.pack(
            '<BBHB',
            makerbot_driver.host_action_command_dict['WAIT_FOR_BUTTON'],
            button,
            timeout,
            optionsField
        )

        self.writer.send_action_payload(payload)

    def reset_to_factory(self):
        """
        Calls factory reset on the EEPROM.  Resets all values to their factory settings.  Also soft resets the board
        """
        payload = struct.pack(
            '<BB',
            makerbot_driver.host_action_command_dict['RESET_TO_FACTORY'],
            0x00
        )

        self.writer.send_action_payload(payload)

    def queue_song(self, song_id):
        """
        Play predefined sogns on the piezo buzzer
        @param int songId: The id of the song to play.
        """
        payload = struct.pack(
            '<BB',
            makerbot_driver.host_action_command_dict['QUEUE_SONG'],
            song_id
        )

        self.writer.send_action_payload(payload)

    def set_build_percent(self, percent):
        """
        Sets the percentage done for the current build.  This value is displayed on the interface board's screen.
        @param int percent: Percent of the build done (0-100)
        """
        payload = struct.pack(
            '<BBB',
            makerbot_driver.host_action_command_dict['SET_BUILD_PERCENT'],
            percent,
            0x00
        )

        self.writer.send_action_payload(payload)

    def display_message(self, row, col, message, timeout, clear_existing, last_in_group, wait_for_button):
        """
        Display a message to the screen
        @param int row: Row to draw the message at
        @param int col: Column to draw the message at
        @param str message: Message to write to the screen
        @param int timeout: Amount of time to display the message for, in seconds.
                       If 0, leave the message up indefinately.
        @param boolean clear_existing: If True, This will clear the existing message buffer and timeout
        @param boolean last_in_group: If true, signifies that this message is the last in a group of messages
        @param boolean wait_for_button: If true, waits for a button to be pressed before clearing the screen
        """
        bitField = 0
        if clear_existing:
            bitField |= 0x01
        if last_in_group:
            bitField |= 0x02
        if wait_for_button:
            bitField |= 0x04

        payload = struct.pack(
            '<BBBBB',
            makerbot_driver.host_action_command_dict['DISPLAY_MESSAGE'],
            bitField, col, row, timeout,
        )
        payload += message
        payload += '\x00'

        self.writer.send_action_payload(payload)

    def build_start_notification(self, build_name):
        """
        Notify the machine that a build has been started.
        If the build_name is too long, we will truncate it to its
        maximum allowed length relative to the makerbot_driver.maximum_payload_length.
        @param str build_name Name of the build
        """
        other_info_in_packet = 7
        if len(build_name) > makerbot_driver.maximum_payload_length - other_info_in_packet:
            build_name = build_name[:makerbot_driver.maximum_payload_length -
                                    other_info_in_packet]
        payload = struct.pack(
            '<BI',
            makerbot_driver.host_action_command_dict[
                'BUILD_START_NOTIFICATION'], 0
        )

        payload += build_name
        payload += '\x00'

        self.writer.send_action_payload(payload)

    def build_end_notification(self):
        """
        Notify the machine that a build has been stopped.
        """
        payload = struct.pack(
            '<BB',
            makerbot_driver.host_action_command_dict['BUILD_END_NOTIFICATION'],
            0,
        )

        self.writer.send_action_payload(payload)

    def get_toolhead_version(self, tool_index):
        """
        Get the firmware version number of the specified toolhead
        @return double Version number
        """
        payload = struct.pack(
            '<H', makerbot_driver.s3g_version)

        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_VERSION'], payload)
        [response_code, version] = makerbot_driver.Encoder.unpack_response(
            '<BH', response)

        return version

    def get_PID_state(self, tool_index):
        """
        Retrieve the state variables of the PID controller.  This is intended for tuning the PID Constants
        @param int tool_index: Which tool index to query for information
        @return dictionary The terms associated with the tool_index'sError Term, Delta Term, Last Output
          and the platform's Error Term, Delta Term and Last Output
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_PID_STATE'])
        [response_code, exError, exDelta, exLast, plError, plDelta, plLast] = makerbot_driver.Encoder.unpack_response('<Bhhhhhh', response)
        PIDVals = {
            "ExtruderError": exError,
            "ExtruderDelta": exDelta,
            "ExtruderLastTerm": exLast,
            "PlatformError": plError,
            "PlatformDelta": plDelta,
            "PlatformLastTerm": plLast,
        }
        return PIDVals

    def get_tool_status(self, tool_index):
        """
        Retrieve some information about the tool, as a status dictionary
        statusDict = {
          ExtruderReady : The extruder has reached target temp
          ExtruderNotPluggedIn : The extruder thermocouple is not detected by the bot
          ExturderOverMaxTemp : The temperature measured at the extruder is greater than max allowed
          ExtruderNotHeating : In the first 40 seconds after target temp was set, the extruder is not heating up as expected
          ExtruderDroppingTemp : After reaching and maintaining temperature, the extruder temp has dropped 30 degrees below target
          PlatformError: an error was detected with the platform heater (if the tool supports one).
            The platform heater will fail if an error is detected with the sensor (thermocouple)
            or if the temperature reading appears to be unreasonable.
          ExtruderError: An error was detected with the extruder heater (if the tool supports one).
            The extruder heater will fail if an error is detected with the sensor (thermocouple) or
            if the temperature reading appears to be unreasonable
          }
         @param int tool_index: The tool we would like to query for information
         @return A dictionary containing status information specified above
       """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_TOOL_STATUS'])

        [resonse_code, bitfield] = makerbot_driver.Encoder.unpack_response(
            '<BB', response)

        bitfield = makerbot_driver.Encoder.decode_bitfield(bitfield)

        returnDict = {
            "ExtruderReady": bitfield[0],
            "ExtruderNotPluggedIn": bitfield[1],
            "ExtruderOverMaxTemp": bitfield[2],
            "ExtruderNotHeating": bitfield[3],
            "ExtruderDroppingTemp": bitfield[4],
            "PlatformError": bitfield[6],
            "ExtruderError": bitfield[7],
        }
        return returnDict

    def set_servo1_position(self, tool_index, theta):
        """
        Sets the tool_index's servo as position 1 to a certain angle
        @param int tool_index: The tool that will be set
        @param int theta: angle to set the servo to
        """
        payload = struct.pack(
            '<B',
            theta
        )

        self.tool_action_command(tool_index, makerbot_driver.slave_action_command_dict[
                                 'SET_SERVO_1_POSITION'], payload)

    def toolhead_abort(self, tool_index):
        """
        Used to terminate a build during printing.  Disables any engaged heaters and motors
        @param int tool_index: the tool which is to be aborted
        """
        self.tool_action_command(
            tool_index, makerbot_driver.slave_action_command_dict['ABORT'])

    def toolhead_pause(self, tool_index):
        """
        This function is intended to be called infrequently by the end user to pause the toolhead
        and make various adjustments during a print
        @param int tool_index: The tool which is to be paused
        """
        self.tool_action_command(
            tool_index, makerbot_driver.slave_action_command_dict['PAUSE'])

    def toggle_motor1(self, tool_index, toggle, direction):
        """
        Toggles the motor of a certain toolhead to be either on or off.  Can also set direction.
        @param int tool_index: the tool's motor that will be set
        @param boolean toggle: The enable/disable flag.  If true, will turn the motor on.  If false, disables the motor.
        @param boolean direction: If true, sets the motor to turn clockwise.  If false, sets the motor to turn counter-clockwise
        """
        bitfield = 0
        if toggle:
            bitfield |= 0x01
        if direction:
            bitfield |= 0x02

        payload = struct.pack(
            '<B',
            bitfield,
        )

        self.tool_action_command(
            tool_index, makerbot_driver.slave_action_command_dict['TOGGLE_MOTOR_1'], payload)

    def set_motor1_speed_RPM(self, tool_index, duration):
        """
        This sets the motor speed as an RPM value
        @param int tool_index : The tool's motor that will be set
        @param int duration : Durtation of each rotation, in microseconds
        """
        payload = struct.pack(
            '<I',
            duration
        )

        self.tool_action_command(tool_index, makerbot_driver.slave_action_command_dict[
                                 'SET_MOTOR_1_SPEED_RPM'], payload)

    def set_motor1_direction(self, tool_index, direction):
        """
        This sets the direction of rotation for the motor
        @param int tool_index: The tool's motor that will be set
        @param boolean direction: If true, sets the motor to turn clockwise.  If false, sets the motor to turn counter-clockwise
        """
        clockwise = 0
        if direction:
            clockwise = 1
        payload = struct.pack(
            '<B',
            clockwise
        )
        self.tool_action_command(tool_index, makerbot_driver.slave_action_command_dict['SET_MOTOR_1_DIRECTION'], payload)

    def get_motor1_speed(self, tool_index):
        """
        Gets the toohead's motor speed in Rotations per Minute (RPM)
        @param int tool_index: The tool index that will be queried for Motor speed
        @return int Duration of each rotation, in miliseconds
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_MOTOR_1_SPEED_RPM'])
        [response_code,
            speed] = makerbot_driver.Encoder.unpack_response('<BI', response)
        return speed

    def get_toolhead_temperature(self, tool_index):
        """
        Retrieve the toolhead temperature
        @param int tool_index: Toolhead Index
        @return int temperature: reported by the toolhead
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_TOOLHEAD_TEMP'])
        [response_code, temperature] = makerbot_driver.Encoder.unpack_response(
            '<BH', response)

        return temperature

    def is_tool_ready(self, tool_index):
        """
        Determine if the tool is at temperature, and is therefore ready to be used.
        @param int tool_index: Toolhead Index
        @return boolean isReady: True if tool is done heating, false otherwise
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['IS_TOOL_READY'])
        [response_code,
            ready] = makerbot_driver.Encoder.unpack_response('<BB', response)

        isReady = False
        if ready == 1:
            isReady = True
        elif ready == 0:
            isReady = False
        else:
            raise makerbot_driver.HeatElementReadyError(ready)

        return isReady

    def read_from_toolhead_EEPROM(self, tool_index, offset, length):
        """
        Read some data from the toolhead. The data structure is implementation specific.
        @param byte offset: EEPROM location to begin reading from
        @param int length: Number of bytes to read from the EEPROM (max 31)
        @return byte array: of data read from EEPROM
        """
        # We can only read 31 bytes
        if length > makerbot_driver.maximum_payload_length - 1:
            raise makerbot_driver.EEPROMLengthError(length)

        payload = struct.pack(
            '<HB',
            offset,
            length
        )

        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['READ_FROM_EEPROM'], payload)

        return response[1:]

    def write_to_toolhead_EEPROM(self, tool_index, offset, data):
        """
        Write some data to the toolhead. The data structure is implementation specific.
        @param int tool_index: Index of tool to access
        @param byte offset: EEPROM location to begin writing to
        @param list data: Data to write to the EEPROM
        """
        code = '<HB'
        packet_length = struct.calcsize('%s%s' % (code, self.tool_query_code))
        # Check the length of data against maximum_payload_length and the compulsory packet values
        # (Including Tool Packet values
        if len(data) > makerbot_driver.maximum_payload_length - packet_length:
            raise makerbot_driver.EEPROMLengthError(len(data))

        payload = struct.pack(
            code,
            offset,
            len(data),
        )

        payload += data

        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['WRITE_TO_EEPROM'], payload)

        if response[1] != len(data):
            raise makerbot_driver.EEPROMMismatchError(response[1])

    def get_platform_temperature(self, tool_index):
        """
        Retrieve the build platform temperature
        @param int tool_index: Toolhead Index
        @return int temperature: reported by the toolhead
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_PLATFORM_TEMP'])
        [response_code, temperature] = makerbot_driver.Encoder.unpack_response(
            '<BH', response)

        return temperature

    def get_toolhead_target_temperature(self, tool_index):
        """
        Retrieve the toolhead target temperature (setpoint)
        @param int tool_index: Toolhead Index
        @return int temperature: that the toolhead is attempting to achieve
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_TOOLHEAD_TARGET_TEMP'])
        [response_code, temperature] = makerbot_driver.Encoder.unpack_response(
            '<BH', response)

        return temperature

    def get_platform_target_temperature(self, tool_index):
        """
        Retrieve the build platform target temperature (setpoint)
        @param int tool_index: Toolhead Index
        @return int temperature: that the build platform is attempting to achieve
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['GET_PLATFORM_TARGET_TEMP'])
        [response_code, temperature] = makerbot_driver.Encoder.unpack_response(
            '<BH', response)

        return temperature

    def is_platform_ready(self, tool_index):
        """
        Determine if the platform is at temperature, and is therefore ready to be used.
        @param int tool_index: Toolhead Index
        @return boolean isReady: true if the platform is at target temperature, false otherwise
        """
        response = self.tool_query(
            tool_index, makerbot_driver.slave_query_command_dict['IS_PLATFORM_READY'])
        [response_code,
            ready] = makerbot_driver.Encoder.unpack_response('<BB', response)

        isReady = False
        if ready == 1:
            isReady = True
        elif ready == 0:
            isReady = False
        else:
            raise makerbot_driver.HeatElementReadyError(ready)

        return isReady

    def toggle_fan(self, tool_index, state):
        """
        Turn the fan output on or off
        @param int tool_index: Toolhead Index
        @param boolean state: If True, turn the fan on, otherwise off.
        """
        if state is True:
            payload = '\x01'
        else:
            payload = '\x00'

        self.tool_action_command(
            tool_index, makerbot_driver.slave_action_command_dict['TOGGLE_FAN'], payload)

    def toggle_extra_output(self, tool_index, state):
        """
        Turn the extra output on or off
        @param int tool_index: Toolhead Index
        @param boolean state: If True, turn the extra output on, otherwise off.
        """

        if state is True:
            payload = '\x01'
        else:
            payload = '\x00'

        self.tool_action_command(tool_index, makerbot_driver.slave_action_command_dict[
                                 'TOGGLE_EXTRA_OUTPUT'], payload)

    def toolhead_init(self, tool_index):
        """
        Resets a certain tool_index to its initialized boot state, which
        consists of:
        resetting target temp to 0, turn off all outputs, detaching all
        servo devices, setting motor speed to 0
        @param int tool_index: The tool to re-initialize
       """
        self.tool_action_command(tool_index,
                                 makerbot_driver.slave_action_command_dict['INIT'])

    def set_toolhead_temperature(self, tool_index, temperature):
        """
        Set a certain toolhead's temperature
        @param int tool_index: Toolhead Index
        @param int Temperature: Temperature to heat up to in Celcius
        """
        payload = struct.pack('<H', temperature)
        self.tool_action_command(tool_index,
                                 makerbot_driver.slave_action_command_dict['SET_TOOLHEAD_TARGET_TEMP'], payload)

    def set_platform_temperature(self, tool_index, temperature):
        """
        Set the platform's temperature
        @param int tool_index: Platform Index
        @param int Temperature: Temperature to heat up to in Celcius
        """
        payload = struct.pack('<H', temperature)

        self.tool_action_command(
            tool_index,
            makerbot_driver.slave_action_command_dict['SET_PLATFORM_TEMP'], payload)

    def toggle_ABP(self, tool_index, state):
        """
        This sets the on/off state of the ABP's conveyor belt
        @param boolean : Turns on or off the ABP's conveyor belt
        """
        enable = 0
        if state:
            enable = 1
        payload = struct.pack(
            '<B',
            enable
        )
        self.tool_action_command(tool_index, makerbot_driver.slave_action_command_dict['TOGGLE_ABP'], payload)

    def set_servo2_position(self, tool_index, theta):
        """
        Sets the tool_index's servo as position 2 to a certain angle
        @param int tool_index: The tool that will be set
        @param int theta: angle to set the servo to
        """
        payload = struct.pack(
            '<B',
            theta
        )
        self.tool_action_command(tool_index, makerbot_driver.slave_action_command_dict['SET_SERVO_2_POSITION'], payload)

    def x3g_version(self, high_bite, low_bite, checksum=0x0000, pid=0xB015):
        """
        Send an x3g_version packet to inform the bot what version
        x3g we are sending and potential checksum for succeeding
        commands.

        @param int high_bite: High bite for version (i.e. 1 for 1.0)
        @param int low_bite: Low bite for version (i.e. 0 for 1.0)
        @param int pid: PID for the bot you want to print to
        @param int checksum: Checksum for succeeding commands
        """
        payload = struct.pack(
        '<BBBBIHBBBBBBBBBBB',
        makerbot_driver.host_action_command_dict['X3G_VERSION'],
        high_bite,
        low_bite,
        0,
        checksum,
        pid,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        )
        self.writer.send_action_payload(payload)

