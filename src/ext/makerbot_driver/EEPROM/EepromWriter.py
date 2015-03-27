"""
An eeprom writer!
"""
from __future__ import (absolute_import)

import json
import struct
import os
import logging

import makerbot_driver


class EepromWriter(object):

    @classmethod
    def factory(cls, s3gObj=None, firmware_version='6.0', software_variant='0x00', working_directory=None):
        """ factory for creating an eeprom reader
        @param s3gObj an makerbot_driver.s3g object
        @param eeprom_map json file.
        @param working_directory container of eeprom_map name file
        """
        map_name = makerbot_driver.EEPROM.constants.eeprom_map_name % (firmware_version, software_variant)
        eeprom_writer = makerbot_driver.EEPROM.EepromWriter(map_name, working_directory)
        eeprom_writer.s3g = s3gObj
        return eeprom_writer

    def __init__(self, map_name=None, working_directory=None):
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
        self.data_map = 'eeprom_data'
        self.data_buffer = []

    def reset_eeprom_completely(self):
        """
        Using the size of the eeprom in the eeprom map, writes "0xFF" to each
        eeprom entry.
        """
        offset = 0
        size = makerbot_driver.EEPROM.constants.total_eeprom_size
        for i in range(size):
            self.s3g.write_to_EEPROM(offset + i, struct.pack('<B', 255))

    def write_entire_map(self, input_map):
        """
        Writes all values defined in input_map to the
        eeprom.  Assumes the map is nested inside an
        entry defined by self.main_map ("eeprom_map")

        @param dict input_map: The input map iterated
          on to write data
        """
        input_values = input_map[self.main_map]
        self._write_map(input_values)
        self.flush_data()

    #TODO: Test me
    def _write_map(self, input_map, context=[]):
        for value in input_map:
            if 'sub_map' in input_map[value]:
                self._write_map(
                    input_map[value]['sub_map'], context=context + [value])
            else:
                data = input_map[value]['value']
                #Strings are stored as unicode, so we must convert them to utf8
                for i in range(len(data)):
                    if isinstance(data[i], unicode):
                        data[i] = data[i].encode("utf8")
                self.write_data(value, data, context)

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

    def write_data(self, name, data, context=None, flush=False):
        if not isinstance(data, list):
            data = [data]
        found_dict, offset = self.get_dict_by_context(name, context)
        data = self.encode_data(data, found_dict)
        self.data_buffer.append([offset, data])
        if flush:
            self.flush_data()

    def flush_data(self):
        for data in self.data_buffer:
            self._flush_out_data(data[0], data[1])

    def _flush_out_data(self, offset, data):
        try:
            self.s3g.write_to_EEPROM(offset, data)
        except makerbot_driver.EEPROMLengthError:
            a, b = self._bifurcate_data(data)
            self._flush_out_data(offset, a)
            self._flush_out_data(offset + len(a), b)

    def _bifurcate_data(self, data):
        length = len(data) / 2
        a = data[:length]
        b = data[length:]
        return a, b

    def good_string_type(self, the_type):
        """
        Given a struct packing code for a string type of primitive,
        determines if its an acceptable code.
        """
        value = False
        value = the_type == 's'
        return value

    def good_floating_point_type(self, the_type):
        """
        Given a struct packing code for a floating_point
        number, determines if it is an acceptable code
        """
        value = False
        for char in the_type:
            value = char.upper() == 'H'
        return value

    def encode_data(self, data, input_dict):
        """
        Given a list of values and an input dict for that value,
        packs then into a byte string.

        @param list values: A list of values to pack
        @param dict input_dict: The input dict for this particular eeprom entry
        @return str: The values packed into a byte string
        """
        if 'mult' in input_dict:
            pack_code = str(input_dict['type'] * int(input_dict['mult']))
        else:
            pack_code = str(input_dict['type'])
        if len(pack_code) is not len(data):
            raise makerbot_driver.EEPROM.MismatchedTypeAndValueError([len(pack_code), len(data)])
        if 'floating_point' in input_dict:
            payload = self.process_floating_point(data, pack_code)
        elif 's' in pack_code:
            payload = self.process_string(data, pack_code)
        else:
            payload = self.process_value(data, pack_code)
        return payload

    def process_value(self, data, the_type):
        payload = ''
        for code, point in zip(the_type, data):
            payload += struct.pack('<%s' % (code), point)
        return payload

    def process_string(self, data, the_type):
        if not self.good_string_type(the_type):
            raise makerbot_driver.EEPROM.IncompatableTypeError(the_type)
        return self.encode_string(data[0])

    def process_floating_point(self, data, the_type):
        if not self.good_floating_point_type(the_type):
            raise makerbot_driver.EEPROM.IncompatableTypeError(the_type)
        payload = ''
        for point in data:
            bits = self.calculate_floating_point(point)
            payload += struct.pack('<BB', bits[0], bits[1])
        return payload

    def encode_string(self, string):
        """
        Packs a string into a byte array
        """
        terminated_string = self.terminate_string(string)
        code = '<%is' % (len(terminated_string))
        return struct.pack(code, terminated_string)

    def terminate_string(self, string):
        return string + '\x00'

    def calculate_floating_point(self, value):
        """
        Given a floating point numer, calculated the two bits
        used to store it.
        """
        min_val = 0
        max_val = 256
        if value < min_val or value > max_val:
            raise FloatingPointError
        #Special case when value is maxed
        if value == max_val:
            bits = (255, 255)
        else:
            high_bit = int(value)
            low_bit = value - high_bit
            low_bit = round(low_bit * 255)
            bits = (high_bit, low_bit)
        return bits
