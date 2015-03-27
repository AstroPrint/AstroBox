from __future__ import absolute_import

import os
import json
import struct
import logging

import makerbot_driver

class EepromRepairer(object):

    def __init__(self, map_name=None, working_directory=None):
        self._log = logging.getLogger(self.__class__.__name__)
        self.map_name = map_name if map_name else makerbot_driver.EEPROM.constants.eeprom_map_name % (
            makerbot_driver.EEPROM.constants.default_version, 
            makerbot_driver.EEPROM.constants.default_software_variant
        )
        self.working_directory = working_directory if working_directory else os.path.abspath(os.path.dirname(__file__))
        path = os.path.join(self.working_directory, self.map_name)
        try:
            with open(path) as f:
                self.eeprom_map = json.load(f)
            if 'eeprom_map' in self.eeprom_map:
                self.eeprom_map = self.eeprom_map['eeprom_map']
        except IOError as e:
            self._log.error("Could not find %s", path)
            raise makerbot_driver.EEPROM.MissingEepromMapError(path)

    def build_packed_data(self, length):
        packed_data = ''
        for i in range(length):
            packed_data += struct.pack('<B', 0xFF)
        return packed_data

    def repair_mapped_region_simple(self):
        self.s3g.reset_to_factory()

    def repair_mapped_region(self, repair_dict):
        constraints = repair_dict['constraints']
        if 'l' == constraints[0]:
            self.repair_mapped_region_list(repair_dict) 
        elif 'm' == constraints[0]:
            self.repair_mapped_region_min_max(repair_dict)
        else:
            self.repair_mapped_region_any(repair_dict)

    def repair_mapped_region_list(self, repair_dict):
        assert 'l' == repair_dict['constraints'][0]
        value = makerbot_driver.EEPROM.parse_out_constraints(repair_dict['constraints'])[1]
        offset = repair_dict['offset']
        data = ''
        for char in repair_dict['type']:
            data += struct.pack('<%s' % (char), value)
        self._flush_out_data(offset, data)

    def repair_mapped_region_min_max(self, repair_dict):
        assert 'm' == repair_dict['constraints'][0]
        value = makerbot_driver.EEPROM.parse_out_constraints(repair_dict['constraints'])[1]
        offset = repair_dict['offset']
        data = ''
        for char in repair_dict['type']:
            data += struct.pack('<%s' % (char), value)
        self._flush_out_data(offset, data)

    def repair_mapped_region_any(self, repair_dict):
        assert 'a' == repair_dict['constraints'][0]
        value = 0
        offset = repair_dict['offset']
        data = ''
        for char in repair_dict['type']:
            data += struct.pack('<%s' % (char), value)
        self._flush_out_data(offset, data)
        
    def repair_unmapped_region(self, bad_offsets):
        sequences = self.build_sequences(bad_offsets)
        for sequence in sequences:
            offset = sequence[0]
            length = len(sequence)
            data = self.build_packed_data(length)
            self._flush_out_data(offset, data)

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

    def build_sequences(self, bad_offsets):
        offsets = bad_offsets[:]
        sequences = []
        while len(offsets) > 0:
            sequence = []
            for i in offsets:
                if len(sequence) == 0:
                    sequence.append(i)
                else:
                    if i - 1 == sequence[-1]:
                        sequence.append(i)
                    else:
                        break
            offsets = offsets[len(sequence):]
            sequences.append(sequence)
        return sequences
