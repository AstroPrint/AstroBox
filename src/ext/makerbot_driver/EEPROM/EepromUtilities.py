import re

def get_eeprom_map_contexts(eeprom_map, context=[]):
    """
    Given an eeprom_map, returns a sorted context for each value

    @param dict eeprom_map: Map of the eeprom
    @param list context: Context we start at
    @return list: List of contexts
    """
    return_contexts = []
    for key in eeprom_map:
        this_context = context+[key]
        if 'sub_map' in eeprom_map[key]:
            return_contexts.extend(get_eeprom_map_contexts(eeprom_map[key]['sub_map'], this_context+['sub_map']))
        else:
            return_contexts.append(this_context)
    return_contexts.sort()
    return return_contexts

def get_offset_by_context(dct, context):
    """
    Given a dict, gets the offset to a subdict given a context

    @param dict dct: Dict to traverse
    @param list context: Context used to derive offset
    @return int: Offset to a certain subdict
    """ 
    offset = 0
    the_context = context[:]
    sub_dct = dct
    while len(the_context) > 1:
        if the_context[0] != 'sub_map':
            hex_val = sub_dct[the_context[0]]['offset']
            offset += int(hex_val, 16)
        sub_dct = sub_dct[the_context[0]]
        the_context = the_context[1:]
    hex_val = sub_dct[the_context[0]]['offset']
    offset += int(hex_val, 16)
    return offset

def get_dict_by_context(dct, context):
    """
    Given a dict, gets a subdict depending on the context

    @param dict dct: Dictionary to traverse
    @param list context: Context used to retrieve the subdict
    @return dict: Subdict targeted by context
    """
    the_context = context[:]
    sub_dct = dct
    while len(the_context) > 1:
        sub_dct = sub_dct[the_context[0]]
        the_context = the_context[1:]
    return sub_dct[the_context[0]]

def parse_out_constraints(constraints):
    """
    Parses constraints out of the string (decods, ints, hex, etc)

    @param str constaints: Constraints for a certain value
    @return list: List of constraints
    """
    the_constraints = constraints.split(',')
    parsed = the_constraints[:1]
    for value in the_constraints[1:]:
        if '0x' in value:
            parsed.append(int(value, 16))
        elif re.search('[0-9]', value):
            parsed.append(int(value))
        else:
            parsed.append(value)
    return parsed

