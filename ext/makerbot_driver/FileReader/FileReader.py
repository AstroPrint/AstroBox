"""
A file parser that decodes an s3g file
"""

from __future__ import absolute_import

import struct
import logging
import os

import makerbot_driver


class FileReader(object):

    def __init__(self):
        self._log = logging.getLogger(self.__class__.__name__)
        self.bytesread = 0

    def ReadBytes(self, count):
        """ Read a number of bytes from the current file.

        Throws a EndOfFileError exception if too few bytes were available.
        @return string Bytes from the file.
        """
        data = self.file.read(count)

        if len(data) != count:
            self._log.debug('{"event":"insufficient_data"}')
            raise makerbot_driver.FileReader.InsufficientDataError

        self.bytesread += count
        return data

    def GetStringBytes(self):
        """Get all bytes associated with a string
        Assuming the next parameter is a null terminated string,
        we read bytes until we find that null terminator
        and return the string.  If we read over the
        packet limit, we raise a StringTooLong error.
        @return The bytes making up a null terminated string
        """
        b = ''
        while True:
            b += self.ReadBytes(1)
            if b == '':  # We just read in an empty string, so we ran out of data
                self._log.debug('{"event":"insufficient_data"}')
                raise makerbot_driver.FileReader.InsufficientDataError
            if len(b) > makerbot_driver.maximum_payload_length:
                self._log.debug('{"event":"string_too_long"}')
                raise makerbot_driver.FileReader.StringTooLongError
            elif b[-1] == '\x00':
                return b

    def GetNextCommand(self):
        """Assuming the file pointer is at a command, gets the next command number
        If ReadBytes raises an InsufficientDataError (indicating no more information
        if available in the file), we throw an EndOfFileError

        @return int The command number
        """
        try:
            cmd = ord(self.ReadBytes(1))
        except makerbot_driver.FileReader.InsufficientDataError:
            raise makerbot_driver.FileReader.EndOfFileError

        # TODO: Break the tool action commands out of here
        if (not cmd in makerbot_driver.slave_action_command_dict.values()) and \
           (not cmd in makerbot_driver.host_action_command_dict.values()):
            self._log.debug('{"event":"bad_read_command", "command":%s}', cmd)
            raise makerbot_driver.FileReader.BadCommandError(cmd)

        return cmd

    def ParseOutParameters(self, formatString):
        """Reads and decodes a certain number of bytes using a specific format string
        from the input s3g file

        @param string formatString: The format string we will unpack from the file
        @return list objects unpacked from the input s3g file
        """
        returnParams = []
        for formatter in formatString:
            if formatter == 's':
                b = self.GetStringBytes()
                formatString = '<' + str(len(b)) + formatter
            else:
                b = self.ReadBytes(struct.calcsize(formatter))
                formatString = '<' + formatter
            returnParams.append(self.ParseParameter(formatString, b))
        return returnParams

    def ParseParameter(self, formatString, bytes):
        """Given a format string and a set of bytes, unpacks the bytes into the given format

        @param string formatString: A format string of format to be used when unpacking bytes with the struct object
        @param bytes: The bytes to be unpacked
        @return The correctly unpacked string
        """
        returnParam = struct.unpack(formatString, bytes)[0]
        #Remove the null terminator from the decoded string if present
        if 's' in formatString and returnParam[-1] == '\x00':
            returnParam = returnParam[:-1]
        return returnParam

    def ParseHostAction(self, cmd):
        try:
            return self.ParseOutParameters(makerbot_driver.FileReader.hostFormats[cmd])
        except KeyError:
            self._log.debug(
                '{"event":"bad_host_command", "bad_command":%s}', cmd)
            raise makerbot_driver.FileReader.BadHostCommandError(cmd)

    def ParseToolAction(self, cmd):
        if cmd != makerbot_driver.host_action_command_dict['TOOL_ACTION_COMMAND']:
            self._log.debug(
                '{"event":"cmd_is_not_tool_action_cmd", "bad_cmd":%s}', cmd)
            raise makerbot_driver.FileReader.NotToolActionCmdError
        data = []
        data.extend(self.ParseOutParameters(makerbot_driver.FileReader.hostFormats[cmd]))
        slaveCmd = data[1]
        try:
            data.extend(self.ParseOutParameters(makerbot_driver.FileReader.slaveFormats[slaveCmd]))
        except KeyError:
            self._log.debug(
                '{"event":"bad_slave_cmd", "bad_cmd":%s}', slaveCmd)
            raise makerbot_driver.FileReader.BadSlaveCommandError(slaveCmd)
        return data

    def ParseNextPayload(self):
        """Gets the next command and returns the parsed commands and associated parameters

        @return list: a list of the cmd and  all information associated with that command
        """
        cmd = self.GetNextCommand()
        if cmd == makerbot_driver.host_action_command_dict['TOOL_ACTION_COMMAND']:
            params = self.ParseToolAction(cmd)
        else:
            params = self.ParseHostAction(cmd)
        return [cmd] + params

    def ReadFile(self, callback=None):
        """Reads from an s3g file until it cant read anymore

        @return payloads: A list of payloads, where each index of
          the list is comprised of one payload
        """
        
        # We try to find the total size of the file we're reading.  If
        # we cant, we set it to one and continue
        try:
            self.totalsize = float(os.stat(self.file.name).st_size)
        except AttributeError as e:
            self.totalsize = 1
        self.bytesread = 0
        payloads = []
        try:
            self._log.debug('{"event":"reading_bytes_from_file", "file":%s}',
                            str(self.file))
            while True:
                payload = self.ParseNextPayload()
                payloads.append(payload)
                if callback:
                    percent = int(self.bytesread / self.totalsize * 100)
                    callback(percent)
        # TODO: We aren't catching partial packets at the end of files here.
        except makerbot_driver.FileReader.EndOfFileError:
            self._log.debug('{"event":"done_reading_file"}')
            return payloads
