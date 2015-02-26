class EepromError(Exception):
    """
    Super class for Eeprom Errors
    """
    def __init__(self, value):
        self.value = value

class NonTerminatedStringError(EepromError):
    """NonTerminatedStringErrors are raised when a string is parsed that does not have a null-terminator on it
    """
    def __init__(self, value):
        self.value = value


class PoorlySizedFloatingPointError(EepromError):
    """A PoorlySizedFloatingPointErrpr is raised when a value is defined as being a mighty board style floating point number, but has a length not equal to 2."""
    def __init__(self, value):
        self.value = value


class IncompatableTypeError(EepromError):
    """An IncompatableTypeError is raised when types than cannot be packed together are packed together.
    """
    def __init__(self, value):
        self.value = value


class MismatchedTypeAndValueError(EepromError):
    """A MismatchedTypeAndValueError is raised when the length of a type does not equal the number of values trying to be packed.
    """
    def __init__(self, value):
        self.value = value


class EntryNotFoundError(EepromError):
    """An EntryNotFoundError is raised when an entry is searched for in the eeprom map, but not found.
    """
    def __init__(self, value):
        self.value = value


class ToolheadSubMapError(EepromError):
    """A ToolheadSubmapError is raised when a we try to lookup a toolhead eeprom value with a sub_map name that is not toolhead_eeprom_offset
    """
    def __init__(self, value):
        self.value = value


class SubMapNotFoundError(EepromError):
    """A SubmapNotFoundError is raised when a submap isnt found in the main eeprom_offsets dictionary.
    """
    def __init__(self, value):
        self.value = value


class SubMapReadError(EepromError):
    """A SubMapReadError is raised when the user attempts to read a SubMap
    """
    def __init__(self, value):
        self.value = value

class MissingEepromMapError(EepromError):
    """Thrown when an Eeprom Map cant be found in the given directory
    """
    def __init__(self, value):
        self.value = value
