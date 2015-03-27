"""
An eeprom reader!
"""

from __future__ import (absolute_import)

import array
import json
import struct
import os
import logging

import makerbot_driver


class EepromReader(object):

    @classmethod
    def factory(cls, s3gObj=None, firmware_version='6.0', software_variant='0x00', working_directory=None):
        """ factory for creating an eeprom reader
       @param s3gObj an makerbot_driver.s3g object
       @param eeprom_map json file.
       @param working_directory container of eeprom_map name file
       """
        map_name = makerbot_driver.EEPROM.constants.eeprom_map_name % (firmware_version, software_variant)
        eeprom_reader = makerbot_driver.EEPROM.EepromReader(map_name, working_directory)
        eeprom_reader.s3g = s3gObj
        return eeprom_reader

    def __init__(self, map_name=None, working_directory=None):
        """ generic constructor.
        @param map_name filename of the map to use. eeprom_map.json if not specifie
        @param working_directory drectory containing the map file name
        """
        self._log = logging.getLogger(self.__class__.__name__)
        self.map_name = map_name if map_name else makerbot_driver.EEPROM.constants.eeprom_map_name % (
            makerbot_driver.EEPROM.constants.default_version, 
            makerbot_driver.EEPROM.constants.default_software_variant
        )
        self.working_directory = working_directory if working_directory else os.path.abspath(os.path.dirname(__file__))
        #Load the eeprom map
        path = os.path.join(self.working_directory, self.map_name)
        try:
            with open(path) as f:
                self.eeprom_map = json.load(f)
        except IOError as e:
            self._log.error("Could not find %s", path)
            raise makerbot_driver.EEPROM.MissingEepromMapError(path)
        #We always start with the main map
        self.main_map = 'eeprom_map'

    #TODO: Test me
    def read_entire_map(self):
        """
        Reads all entries on a mapped eeprom using an eeprom_map as
        a guide.

        @return dict: The read eeprom map
        """
        input_map = self.eeprom_map[self.main_map]
        self._read_map(input_map)
        return {self.main_map: input_map}

    def _read_map(self, input_map, context=[]):
        for value in input_map:
            if 'sub_map' in input_map[value]:
                self._read_map(
                    input_map[value]['sub_map'], context=context + [value])
            else:
                input_map[value]['value'] = self.read_data(value, context)

    def read_data(self, name, context=None):
        the_dict, offset = self.get_dict_by_context(name, context)
        return self.read_from_eeprom(the_dict, offset)

    def get_dict_by_context(self, name, context=None):
        """
        Due to the nested nature of the eeprom map, we need to be given
        some context when reading values.  In this instance, we are given the
        actual value name we want to read, in addition to its precise location
        (i.e. We can write the 'P' value for PID constants in both:
            "T0_DATA_BASE", "EXTRUDER_PID_BASE", D_TERM_OFFSET" and
            "T0_DATA_BASE", "HBP_PID_BASE", D_TERM_OFFSET" and

        @param str name: The name of the value we want to read
        @param args: The sub_map names of the eeprom_map
        @return value: The value we read from the eeprom
        """
        the_dict = self.eeprom_map.get(self.main_map)
        offset = 0
        if context:
            for c in context:
                offset += int(the_dict[c]['offset'], 16)
                the_dict = the_dict.get(c)['sub_map']
        the_dict = the_dict[name]
        offset += int(the_dict['offset'], 16)
        return the_dict, offset

    def read_from_eeprom(self, input_dict, offset):
        """
        Reads information off an eeprom, starting from a given offset.

        @param dict input_dict: Dictionary with information required
        to read off the eeprom.
        @param int offset: The offset to start reading from
        @return value: The values read from the eeprom
        """
        if 'sub_map' in input_dict:
            return_val = self.read_eeprom_sub_map(input_dict, offset)
        elif 'floating_point' in input_dict:
            return_val = self.read_floating_point_from_eeprom(
                input_dict, offset)
        elif input_dict['type'] == 's':
            return_val = self.read_string_from_eeprom(input_dict, offset)
        else:
            return_val = self.read_value_from_eeprom(input_dict, offset)
        return return_val

    def read_string_from_eeprom(self, input_dict, offset, default='eeprom_err'):
        """
        Given an input dict with a length, returns a string
        of that length.

        @param dict input_dict: A dict of values used to read
          information off the eeprom
        @param int offset: The offset to read from
        @return str: The read string
        """
        #add one for the null terminator
        val = self.s3g.read_from_EEPROM(offset, int(input_dict['length']))
        return [self.decode_string(val,)]

    def read_eeprom_sub_map(self, input_dict, offset):
        """
        Begins reading an eeprom sub_map off the eeprom.  An eeprom
        sub-map is a mapping of eeprom values that begins at a certain
        position.  Toolhead eeprom offsets and acceleration offsetse
        are held in sub_maps.

        @param dict input_dict: Dictionary with information required
        to read off the eeprom.
        @param int offset: The offset to start reading from
        @return dict: The submap read off the eeprom
        """
        raise makerbot_driver.EEPROM.SubMapReadError(input_dict)

    def read_floating_point_from_eeprom(self, input_dict, offset):
        """
        Given an input dict and offset, reads floating point numbers
        off the eeprom and returns them

        @param dict input_dict: Dictionary with information required
        to read off the eeprom.
        @param int offset: The offset to start reading from.
        """
        unpack_code = input_dict['type']
        for c in unpack_code:
            if not c.upper() == 'H':
                raise makerbot_driver.EEPROM.PoorlySizedFloatingPointError(unpack_code)
        fp_vals = []
        for i in range(len(input_dict['type'])):
            size = struct.calcsize(input_dict['type'][i])
            fp = self.read_and_unpack_floating_point(offset + size * i)
            fp_vals.append(fp)
        return fp_vals

    def read_and_unpack_floating_point(self, offset):
        """
        Given an offset, reads a floating point value
        off an eeprom.

        @param int offset: The offset to read from
        @return int: The floating point number.
        """
        high_bit = self.s3g.read_from_EEPROM(offset, 1)
        high_bit = self.unpack_value(high_bit, 'B')[0]
        low_bit = self.s3g.read_from_EEPROM(offset + 1, 1)
        low_bit = self.unpack_value(low_bit, 'B')[0]
        return self.decode_floating_point(high_bit, low_bit)

    def read_value_from_eeprom(self, input_dict, offset):
        """
        Given an input dict with type information, and an offset,
        pulls that data from the eeprom and unpacks it. Reads value
        type by type, so we dont run into any read-too-much-info
        errors.

        @param dict input_dict: Dictionary with information required
        to read off the eeprom.
        @param int offset: The offset we read from on the eeprom
        @return list: The pieces of data we read off the eeprom
        """
        if 'mult' in input_dict:
            unpack_code = str(input_dict['type'] * int(input_dict['mult']))
        else:
            unpack_code = str(input_dict['type'])
        data = []
        for char in unpack_code:
            size = struct.calcsize(char)
            #Get the value to unpack
            val = self.s3g.read_from_EEPROM(offset, size)
            data.extend(self.unpack_value(val, char))
            offset += size
        return data

    def unpack_value(self, value, the_type):
        """
        Given a value and code, puts the value into an
        array and unpacks the value.

        @param bytearray value: The value to unpack
        @param str code: The type of info in the bytearray
        @return value: The information unpacked from value
        """
        value = array.array('B', value)
        return struct.unpack('<%s' % (the_type), value)

    def decode_string(self, instring, default='eeprom_err'):
        """
        Given a string s, determines if its a valid string
        and returns it without the null terminator.

        @param str s: The string as an interable with a null terminator
        @return str: The string w/o a null terminator
        """
        string = ''
        for char in instring:
            if char == 0:
                return string
            string += chr(char)
        #log error
        return default
        #raise NonTerminatedStringError(s)

    def decode_floating_point(self, high_bit, low_bit):
        """
        Given a high_bit and low_bit, calculated a floating
        point numner.

        @param int high_bit: The first bit that determines the integer
        @param int low_bit: The second bit that determines the decimal
        @return int float: The calculated floating point number
        """
        value = high_bit + (low_bit / 255.0)
        value = round(value, 2)
        return value
