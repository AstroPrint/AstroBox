import warnings


class GcodeError(ValueError):
    """
    Gcode errrors are raised when the gcode parser encounters an invalid line
    """
    def __init__(self):
        self.values = {}

    def __str__(self):
        returnStr = ''
        for key in self.values:
            v = str(self.values[key])
            v = v.rstrip(
                '\n')  # Line commands have carriage returns
            returnStr += key + ': ' + v + '\n'
        returnStr = returnStr.rstrip('\n')  # Remove final semicolon
        return returnStr


class CommentError(GcodeError):
    """
    A comment error is raised if an closing parenthesis ) is found without a previous
    opening parenthesis (.
    #TODO: Add line number, full text of line.
    """


class InvalidCodeError(GcodeError):
    """
    An invalid code error is raised if a code is found that is not a roman character.
    #TODO: add line number, code.
    """


class RepeatCodeError(GcodeError):
    """
    A repeat code error is raised if a single code is repeated multiple times in a gcode
    line (for example: G0 G0)
    #TODO: add line number, code.
    """


class MultipleCommandCodeError(GcodeError):
    """
    A repeat code error is raised if both a g and m code are present on the same line
    line (for example: G0 M0)
    #TODO: add line number, code.
    """


class LinearInterpolationError(GcodeError):
    """
    A G1 (Linear Interpolation) command can have either an E code defined or both
    the A and B registers defined.  If both sets are defined, we throw this error.
    """


class ConflictingCodesError(GcodeError):
    """
    A ConflictingCodesError is thrown when two or more codes are present that are
    not allowed to be together.
    I.E. EAB codes are wrapped together in a G1 command
    """


class ExtraneousCodeError(GcodeError):
    """
    An extraneous code error is raised when a code is found in a command that doesn't support it.
    """


class UnrecognizedCommandError(GcodeError):
    """
    An UnrecognizedCodeError is thrown when a gcode is parsed out that is not recognized
    """


class UnspecifiedAxisLocationError(GcodeError):
    """
    An UnspecifiedLocationError is thrown when a movement command is attempted
    without specifying all 5 [x, y, z, a, b] axes
    """


class NoToolIndexError(GcodeError):
    """
    A NoToolIndexError is thrown if a commad that requires a tool index
    to be set is being executed without a tool index set.
    """


class MissingCodeError(GcodeError):
    """
    A MissingCodeError is thrown if a command that requires a certain
    code is missing that code.
    """


class VectorLengthZeroError(GcodeError):
    """
    A VectorLengthZeroError is thrown when a DDA speec is calculated
    for a vector with length 0
    """


class InvalidFeedrateError(GcodeError):
    """
    An InvalidFeedrateError is thrown when a feedrate <0 is given for a movement command
    """

class NoFeedrateSpecifiedError(GcodeError):
    """
    Raised when no feedrate is specified in the codes and the state machine has no feedrate set
    """


class BadPercentageError(GcodeError):
    """
    A BadPercentageError is thrown when a set build percent command is received with an invalid percentage.
    """


class NoBuildNameError(GcodeError):
    """
    A NoBuildNameError is thrown when a build is
    started without a build name set
    """


class ImproperGcodeEncodingError(GcodeError):
    """
    An ImproperGcodeEncodingError is thrown when a Gcode Command is encountered that is not
    encoded in either ASCII or unicode.
    """


class UndefinedVariableError(GcodeError):
    """
    An UndefinedVariableError is thrown when a variable is encountered that is not defined
    in the given environment.
    """


class ImproperVariableError(GcodeError):
    """
    An ImproperVariableError is thrown when a variable that is not prefixed with a '#' is
    defined in the environment.
    """


class CalculateHomingDDAError(GcodeError):
    """
    A CalculateHomingDDAError is raised when an empty max_feedrates list or spm_list has been
    passed in.
    """


class InvalidOffsetError(GcodeError):
    """
    An InvalidOffsetError is raised when an offset defined by the P code in a G10 command
    is not a valid value (1, 2)
    """
