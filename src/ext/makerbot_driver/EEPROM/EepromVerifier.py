"""
A utility to read and eeprom and discern its "goodness"
"""
import json
import os
import re
import struct
import logging

import makerbot_driver

class EepromVerifier(object):

    def __init__(self, hex_path, map_name=None, working_directory=None):
        self._log = logging.getLogger(self.__class__.__name__)
        self.hex_path = hex_path
        self.working_directory = working_directory if working_directory else os.path.abspath(os.path.dirname(__file__))
        self.map_name = map_name if map_name else makerbot_driver.EEPROM.constants.eeprom_map_name % (
            makerbot_driver.EEPROM.constants.default_version, 
            makerbot_driver.EEPROM.constants.default_software_variant
        )
        path = os.path.join(self.working_directory, self.map_name)
        try:
            with open(path) as f:
                self.eeprom_map = json.load(f)
            if 'eeprom_map' in self.eeprom_map:
                self.eeprom_map = self.eeprom_map['eeprom_map']
        except IOError as e:
            self._log.error("Could not find %s", path)
            raise makerbot_driver.EEPROM.MissingEepromMapError(path)

        self.hex_map, self.hex_flags = self.parse_hex_file(self.hex_path)

    def validate_eeprom(self):
        """
        Main validator loop. Checks EEPROM in two steps.
        Step 1:Gets a list of contexts, gets that context's offset
        and constraints.  Grabs the correct value from the hex_map, and ensures the value
        falls within those constraints.  If a value is encountered that does not, return False.

        Step 2: Check the unmapped regions of the EEPROM.  Any values that are flagged as False
        in the hex_map, they are assumed to be unmapped and checked for 0xFF.  Return False if any
        values arent 0xFF

        @return bool: True if the eeprom is acceptable, false otherwise
        @return bad_entries: Tuple describing the entry that caused the failure.
        """
        good_eeprom = True 
        bad_entries = {'mapped_entries': []}
        contexts = makerbot_driver.EEPROM.get_eeprom_map_contexts(self.eeprom_map)
        for context in contexts:
            sub_dct = makerbot_driver.EEPROM.get_dict_by_context(self.eeprom_map, context)
            if 'constraints' not in sub_dct:
                pass
            else:
                offset = makerbot_driver.EEPROM.get_offset_by_context(self.eeprom_map, context)
                all_types = sub_dct['type']
                if 'mult' in sub_dct:
                    all_types *= int(sub_dct['mult'])
                for char in all_types:
                    char = str(char) # Convert from unicode
                    if 's' == char:
                        # The String needs an explicit length
                        type_length = int(sub_dct['length'])
                        value = self.get_string(offset, type_length)
                        char_offset = type_length
                    else:
                        if 'floating_point' in sub_dct:
                            value = self.get_float(offset, char)
                        else:
                            value = self.get_number(offset, char)
                        char_offset = struct.calcsize(char)
                    constraints = sub_dct['constraints']
                    if not self.check_value_validity(value, constraints):
                        good_eeprom = False
                        bad_entries['mapped_entries'].append({
                            'offset': offset,
                            'type': char,
                            'constraints': sub_dct['constraints'],
                            'value': value,
                            'context': context,
                        })
                    offset += char_offset
        unmapped_validity, unmapped_errors = self.check_unread_values()
        bad_entries.update(unmapped_errors)
        return unmapped_validity and good_eeprom, bad_entries


    def parse_hex_file(self, hex_filepath):
        """
        Takes a .hex file of intel flavor of an AVR EEPROM read by AVRDUDE
        and turns it into a dict, where each byte has its own key depending on its
        offset from 0.

        @param str hex_filepath: Path to the hexfile
        @return dict hex_map: Map of the hex file
        @return dict flags: A flag for each entry.  Initialized as true, and flipped to True
            when read
        """
        hex_map = {}
        flags = {}
        regex = ":[0-9A-Fa-f]{2}([0-9A-Fa-f]{4})[0-9A-Fa-f]{2}([0-9A-Fa-f]*?)[0-9A-Fa-f]{2}$"
        runner = 0
        with open(hex_filepath) as f:
            for line in f:
                match = re.match(regex, line)
                # A second group of 0 means theres no more info to read, so we need to break
                if len(match.group(2)) == 0:
                    break
                # The hex file should have byte offsets in the beginning of the line we can check against
                expected_offset = int('0x%s' % (match.group(1)), 16)
                values = match.group(2)
                assert(expected_offset == runner)
                assert(len(values) % 2 == 0)
                # Take all the bytes in this line and put them in a map
                while len(values) > 0:
                    byte = values[:2]
                    hex_map[runner] = byte.upper()
                    flags[runner] = False
                    values = values[2:]
                    runner += 1
        return hex_map, flags

    def check_value_validity(self, value, constraints):
        """
        Parses the constraints out of the string passed in, and checks the values validity
        based on those constraints

        @param value: Value to check.  Can be of varied type
        @retrun bool: True if value is valid, false otherwise
        """
        constraints = makerbot_driver.EEPROM.parse_out_constraints(constraints)
        if constraints[0] == 'l':
            return self.check_value_validity_list(value, constraints)
        elif constraints[0] == 'm':
            return self.check_value_validity_min_max(value, constraints)
        elif constraints[0] == 'a': 
            return True

    def check_value_validity_list(self, value, constraint):
        return value in constraint[1:]

    def check_value_validity_min_max(self, value, constraint):
        return value <= constraint[2] and value >= constraint[1]

    def get_number(self, offset, the_type):
        """
        Given a lenth and an offset, retrieves a nummber.  Expects to only
        unpack one value (i.e. One signed int)

        @param int offset: Offset to start at
        @param int length: Length to read
        @return int: Int read
        """
        assert len(the_type) == 1
        length = struct.calcsize(the_type)
        hex_val = ''
        for i in range(offset, offset+length):
            self.hex_flags[i] = True
            hex_val += self.hex_map[i]
        hex_val = struct.unpack('<%s' % (the_type), hex_val.decode('hex'))[0]
        return hex_val

    def get_float(self, offset, the_type='H'):
        """
        Given a length and an offset, retrieves a floating point value.  Expects 
        to only unpack one float value

        @param int offset: Offset to start at
        @param int length: Length to read
        @return float: Float read
        """
        assert len(the_type) == 1
        vals = []
        length = struct.calcsize(the_type)
        for i in range(offset, offset+length):
            self.hex_flags[i] = True
            # We unpack the two bytes separately to calc the floating point
            val = struct.unpack('<B', self.hex_map[i].decode('hex'))[0]
            vals.append(val)
        special_float = vals[0] + vals[1] / 255.0
        return special_float 

    def get_string(self, offset, length):
        """
        Given a length and an offset, retrieves a string from a the hex map

        @param int offset: Offset to start at
        @param int lenght: Lengt of the variable

        @return str: Read string
        """
        string = ""
        for i in range(offset, offset+length):
            self.hex_flags[i] = True
            char = chr(int(self.hex_map[i], 16))
            string += char
        return string

    def check_unread_values(self):
        """
        Iterates through all flags and, if one if False, checks to make
        sure its 0xFF.  Unmapped regions should stay as 0xFF, and if we 
        havent read it we can assume its supposed to be unmapped.

        @return bool: If all unmapped values were 0xFF or not
        @return dict: Bad offsets in the unmapped eeprom
        """
        all_good = True
        unmapped_value = "FF"
        bad_values = {'unmapped_entries': []}
        for key in self.hex_flags:
            if self.hex_flags[key] is False:
                if not self.hex_map[key].upper() == unmapped_value:
                    all_good = False
                    bad_values['unmapped_entries'].append(key)
        return all_good, bad_values
