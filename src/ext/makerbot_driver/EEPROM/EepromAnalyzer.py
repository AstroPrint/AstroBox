"""
Analyzes the eeprom map in the Mightyboards Source code's
Eeprom.hh file.  Expects blocks of information in the form of:
//$BEGIN_ENTRY
//$S:<some size>
const static uint16_t <some name> = <some address>
"""

import re


class EndOfNamespaceError(IOError):
    def __init__(self):
        pass


class EndOfEepromError(IOError):
    def __init__(self):
        pass

import json
import optparse


class eeprom_analyzer(object):

    def __init__(self, input_fh, output_fh, include_ignore=False):
        self.include_ignore = include_ignore
        self.ignore_flag = 'ignore'
        self.output_fh = output_fh
        self.input_fh = input_fh
        self.eeprom_map = {}  # Contains entries and offsets
        self.eeprom_data = {}  # Contains data about the eeprom (i.e. length)
        self.eeprom_info = 'eeprom_info'
        self.info_marker = '$BEGIN_INFO_ENTRY'

    def parse_file(self):
        self.eeprom_map = {}
        try:
            while True:
                namespace_name = self.find_next_namespace().lower()
                namespace = {}
                try:
                    while True:
                        data = {}
                        marker = self.find_next_entry()
                        #At this point we are on a line thats supposed to have variables
                        variables = self.parse_out_variables(
                            self.input_fh.readline())
                        #AT this point we are at the variable declaration in the .hh file
                        #Begin creating the dict for this entry
                        #Parse all variables and add them to the dict
                        variable_dict = {}
                        for variable in variables:
                            variable = variable.split(':')
                            variable_dict[variable[0]] = variable[1]
                        if self.info_marker in marker:
                            name = variable_dict['name']
                            del(variable_dict['name'])
                        else:
                            (name, location) = self.parse_out_name_and_location(
                                self.input_fh.readline())
                            data['offset'] = location
                        data.update(variable_dict)
                        if self.ignore_flag in data and not self.include_ignore:
                            pass
                        else:
                            namespace[name] = data
                except EndOfNamespaceError:
                    if namespace_name == self.eeprom_info:
                        self.eeprom_data = namespace
                    else:
                        self.eeprom_map[namespace_name] = namespace
        except EndOfEepromError:
            collated_map = {'eeprom_info': self.eeprom_data, 'eeprom_map':
                            self.collate_maps(self.eeprom_map['eeprom_offsets'])}
            self.dump_json(collated_map)

    def find_next_entry(self):
        namespace_end = '}'
        entry_line = re.compile('[\s]*\/\/\$BEGIN_ENTRY|[\s]*\/\/\$BEGIN_INFO_ENTRY')
        line = self.input_fh.readline()
        while not re.match(entry_line, line):
            if namespace_end in line:
                raise EndOfNamespaceError
            line = self.input_fh.readline()
        return line

    def find_next_namespace(self):
        """
        Reads lines from the file until a line that
        starts with namespace is encountered.  The name
        of that namespace is then parsed out and returned.

        @return str name: The name of the current namespace
        """
        namespace = 'namespace'
        end_of_eeprom = '#endif // EEPROMMAP_HH'
        line = self.input_fh.readline()
        while not line.startswith(namespace):
            if end_of_eeprom in line:
                raise EndOfEepromError
            line = self.input_fh.readline()
        return self.parse_out_namespace_name(line)

    def parse_out_namespace_name(self, line):
        """
        Given a line in the form of
          "namespace <name> {"
        parses out the name

        @param str line: The line with the namespace
        @return str name: The name of the namespace
        """
        line = line.strip()
        for s in ['\n', '\r', '\t', '{']:
            line = line.rstrip(s)
        line = line.lstrip('namespace')
        line = line.replace(' ', '')
        return line

    def parse_out_name_and_location(self, line):
        """
        Given a line in the form of:
          const static uint16_t <name> = <location>;
        parses out the name and location.
        If we get a line not of this form, we will fail.

        @param str line: the line we want information from
        @return tuple: Information in the form of (name, location)
        """
        before_semi_regex = "(.*?);"
        match = re.search(before_semi_regex, line)
        substring = match.group(1)
        for w in ['const', 'static', 'uint16_t']:
            substring = substring.replace(w, '')
        substring = substring.replace('\t', '')
        substring = substring.replace(" ", "")
        (name, location) = substring.split("=")
        return name, location

    def parse_out_variables(self, line):
        line = line.strip()
        for s in ['\n', '\r', '\t', ]:
            line = line.rstrip(s)
        line = line.lstrip('//')
        parts = line.split('$')
        for i in range(len(parts)):
            parts[i] = parts[i].lstrip(' ')
            parts[i] = parts[i].rstrip(' ')
        #Dont return the first, since its empty
        return parts[1:]

    def dump_json(self, eeprom_map):
        output = json.dumps(eeprom_map, sort_keys=True, indent=2)
        self.output_fh.write(output)

    def collate_maps(self, the_map):
        """
        Iterates over all entries in a given map and, if necessary,
        inserts a submap where needed.  All entries' submaps point to 
        a namespace of the same name.
        """
        collated_map = the_map
        for key in the_map:
            if 'eeprom_map' in the_map[key]:
                sub_map_name = the_map[key]['eeprom_map']
                collated_map[key]['sub_map'] = self.eeprom_map[sub_map_name]
                self.collate_maps(collated_map[key]['sub_map'])
        return collated_map

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-i', '--input_fh', dest='input_fh',
                      help='The file you would like to parse',
                      default='EepromMap_5.6.hh')
    parser.add_option('-o', '--output_fh', dest='output_fh',
                      help='where you would like to save the map to',
                      )
    parser.add_option('--include-ignore', dest='include_ignore',
                        action='store_true', help='include values intended to be ignored',
                        default=False
    )
    (options, args) = parser.parse_args()
    ea = eeprom_analyzer(
        open(options.input_fh), open(options.output_fh, 'w'), include_ignore=options.include_ignore)
    ea.parse_file()
