from __future__ import absolute_import
import exceptions
import math

import makerbot_driver


def extract_comments(line):
    """
    Parse a line of gcode, stripping semicolon and parenthesis-separated comments from it.
    @param string line gcode line to read in
    @return tuple containing the non-comment portion of the command, and any comments
    """

    # Anything after the first semicolon is a comment
    semicolon_free_line, x, comment = line.partition(';')

    paren_count = 0
    command, x, paren_comment = semicolon_free_line.partition('(')
    unified_comment = '%s%s' % (paren_comment, comment)

    return command, unified_comment


def parse_command(command):
    """
    Parse the command portion of a gcode line, and return a dictionary of found codes and their respective values, and a list of found flags. Codes with integer values will have an integer type, while codes with float values will have a float type
    @param string command Command portion of a gcode line
    @return tuple containing a dict of codes, list of flags.
    """
    codes = {}
    flags = []

    pairs = command.split()
    for pair in pairs:
        code = pair[0]

        # If the code is not a letter, this is an error.
        if not code.isalpha():
            gcode_error = makerbot_driver.Gcode.InvalidCodeError()
            gcode_error.values['InvalidCode'] = code
            raise gcode_error

        # Force the code to be uppercase.
        code = code.upper()

        # If the code already exists, this is an error.
        if code in codes.keys():
            gcode_error = makerbot_driver.Gcode.RepeatCodeError()
            gcode_error.values['RepeatedCode'] = code
            raise gcode_error

        # Don't allow both G and M codes in the same line
        if (code == 'G' and 'M' in codes.keys()) or \
           (code == 'M' and 'G' in codes.keys()):
            raise makerbot_driver.Gcode.MultipleCommandCodeError()

        # If the code doesn't have a value, we consider it a flag, and set it to true.
        if len(pair) == 1:
            flags.append(code)

        else:
            try:
                codes[code] = int(pair[1:])
            except exceptions.ValueError:
                codes[code] = float(pair[1:])

    return codes, flags


def parse_line(line):
    """
    Parse a line of gcode into a map of codes, and a comment field.
    @param string line: line of gcode to parse
    @return tuple containing a dict of codes, a list of flags, and a comment string
    """

    command, comment = extract_comments(line)
    codes, flags = parse_command(command)

    return codes, flags, comment


def check_for_extraneous_codes(codes, allowed_codes):
    """ Check that all of the codes are expected for this command.

    Throws an InvalidCodeError if an unexpected code was found
    @param list codes: list of codes to check
    @param list allowed_codes: list of allowed codes
    """
    #TODO Change the way we add in G and M commands.  Its kinda...bad?
    allowed_codes += "GM"
    difference = set(codes) - set(allowed_codes)

    if len(difference) > 0:
        badCodes = ''  # TODO: can this be stringified in a more straightforward manner?
        for code in difference:
            badCodes += code
        gcode_error = makerbot_driver.Gcode.InvalidCodeError()
        gcode_error.values['InvalidCodes'] = code
        raise gcode_error


def parse_out_axes(codes):
    """Given a list of codes, returns a list of all present axes

    @param list codes: Codes parsed out of the gcode command
    @return list: List of axes in codes
    """
    axesCodes = 'XYZAB'
    parsedAxes = set(axesCodes) & set(codes)
    return list(sorted(parsedAxes))


def variable_substitute(line, environment):
    """
    Given a dict of variables and their definitions with a line ,
    replace all instances of variables with their respective
    definition in the line.

    @param string Line: A line that we will be subjected to variable
        replace
    @param dict environment: A set of variables and definitions that will
        be used to execute variable substitution.
    """
    variableDelineator = '#'
    for key in environment:
        #Cast into strings to get rid of unicode
        variable_key = str(variableDelineator + key)
        variable_value = str(environment[key])
        line = line.replace(variable_key, variable_value)
    if '#' in line:
        raise makerbot_driver.Gcode.UndefinedVariableError
    return line


def calculate_euclidean_distance(minuend, subtrahend):
    """
    Given two points of the same dimension, calculates their
    euclidean distance

    @param list minuend: 5D vector to be subracted from
    @param list subtrahend: 5D vector to subtract from the minuend
    @param int distance: Distance between the two points
    """
    if not len(minuend) == len(subtrahend):
        raise makerbot_driver.PointLengthError("Expected identical lengths, instead got %i %i" % (len(minuend), len(subtrahend)))
    distance = 0.0
    for m, s in zip(minuend, subtrahend):
        distance += pow(m - s, 2)
    distance = math.sqrt(distance)
    return distance


def calculate_vector_difference(minuend, subtrahend):
    """ Given two 5d vectors represented as lists, calculates their
    difference (minued - subtrahend)

    @param list minuend: 5D vector to be subracted from
    @param list subtrahend: 5D vector to subtract from the minuend
    @return list difference
    """
    if len(minuend) != 5:
        raise makerbot_driver.PointLengthError(
            "Expected list of length 5, got length %i" % (len(minuend)))
    if len(subtrahend) != 5:
        raise makerbot_driver.PointLengthError(
            "Expected list of length 5, got length %i" % (len(subtrahend)))

    difference = []
    for m, s in zip(minuend, subtrahend):
        difference.append(m - s)

    return difference


def multiply_vector(factor_a, factor_b):
    """ Given two 5d vectors represented as lists, calculates their product.

    @param list factor_b: 5D vector
    @param list factor_b: 5D vector
    @return list product
    """

    product = []
    for a, b in zip(factor_a, factor_b):
        product.append(a * b)

    return product


def calculate_vector_magnitude(vector):
    """ Given a 5D vector represented as a list, calculate its magnitude

    @param list vector: A 5D vector
    @return magnitude of the vector
    """
    if len(vector) != 5:
        raise makerbot_driver.errors.PointLengthError(
            "Expected list of length 5, got length %i" % (len(vector)))

    magnitude_squared = 0
    for d in vector:
        magnitude_squared += pow(d, 2)

    magnitude = pow(magnitude_squared, .5)

    return magnitude


def calculate_unit_vector(vector):
    """ Calculate the unit vector of a given 5D vector

    @param list vector: A 5D vector
    @return list: The 5D equivalent of the vector
    """
    if len(vector) != 5:
        raise makerbot_driver.errors.PointLengthError(
            "Expected list of length 5, got length %i" % (len(vector)))

    magnitude = calculate_vector_magnitude(vector)

    # Check if this is a null vector
    if magnitude == 0:
        return [0, 0, 0, 0, 0]

    unitVector = []
    for val in vector:
        unitVector.append(val / magnitude)

    return unitVector


def get_safe_feedrate(displacement_vector, max_feedrates, target_feedrate):
    """Given a displacement vector and target feedrate, calculates the fastest safe feedrate

    @param list displacement_vector: 5d Displacement vector to consider, in mm
    @param list max_feedrates: Maximum feedrates for each axis, in mm
    @param float target_feedrate: Target feedrate for the move, in mm/s
    @return float Achievable movement feedrate, in mm/s
    """

    # Calculate the axis components of each vector
    magnitude = calculate_vector_magnitude(displacement_vector)

    # TODO: What kind of error to throw here?
    if magnitude == 0:
        raise makerbot_driver.Gcode.VectorLengthZeroError()

    if target_feedrate <= 0:
        raise makerbot_driver.Gcode.InvalidFeedrateError()

    actual_feedrate = target_feedrate

    # Iterate through each axis that has a displacement
    for axis_displacement, max_feedrate in zip(displacement_vector, max_feedrates):

        axis_feedrate = float(
            target_feedrate) / magnitude * abs(axis_displacement)

        if axis_feedrate > max_feedrate:
            actual_feedrate = float(
                max_feedrate) / abs(axis_displacement) * magnitude

    return actual_feedrate


def find_longest_axis(vector):
    """ Determine the index of the longest axis in a 5D vector.

    @param list vector: A 5D vector
    @return int: The index of the longest vector
    """
    if len(vector) != 5:
        raise makerbot_driver.errors.PointLengthError(
            "Expected list of length 5, got length %i" % (len(vector)))

    max_value_index = 0
    for i in range(1, 5):
        if abs(vector[i]) > abs(vector[max_value_index]):
            max_value_index = i

    return max_value_index


def calculate_DDA_speed(initial_position, target_position, target_feedrate, max_feedrates, steps_per_mm):
    """ Given an initial position, target position, and target feedrate, calculate an achievable
    travel speed.

    @param initial_position: 5D starting position of the move, in mm
    @param target_position: 5D target position to move to, in mm
    @param target_feedrate: Requested feedrate, in mm/s (TODO: Is this correct)
    @param max_feedrates: 5D vector of maximum feedrates, in mm/s
    @param steps_per_mm: 5D vector of steps per milimeters conversion, in steps/mm
    @return float ddaSpeed: The speed in us/step we move at
    """

    # First, figure out where we are moving to.
    displacement_vector = calculate_vector_difference(
        target_position, initial_position)

    # Throw an error if we aren't moving anywhere
    # TODO: Should we do something else here?
    if calculate_vector_magnitude(displacement_vector) == 0:
        raise makerbot_driver.Gcode.VectorLengthZeroError

    # Now, correct the target speedrate to account for the maximum feedrate
    actual_feedrate = get_safe_feedrate(
        displacement_vector, max_feedrates, target_feedrate)

    # Find the magnitude of the longest displacement axis. this axis has the most steps to move
    displacement_vector_steps = multiply_vector(
        displacement_vector, steps_per_mm)
    longest_axis = find_longest_axis(displacement_vector_steps)

    fastest_feedrate = float(abs(displacement_vector[longest_axis])) / calculate_vector_magnitude(displacement_vector) * actual_feedrate
    # Now we know the feedrate of the fastest axis, in mm/min. Convert it to us/step.
    dda_speed = compute_DDA_speed(
        fastest_feedrate, abs(steps_per_mm[longest_axis]))

    return dda_speed


def compute_DDA_speed(feedrate, spm):
    """
    Given a feedrate in mm/min, and SPM in steps/mm, calculate its DDA
    speed, in microSeconds/step.

    @param int feedrate: The desired movement speed in mm/min
    @param float spm: The steps per mm we use to get the DDA speed
    @return float dda_speed: The dda speed we use
    """
    second_const = 60
    micro_second_const = 1000000
    dda_speed = second_const * micro_second_const / (feedrate * spm)
    return dda_speed


def calculate_homing_DDA_speed(feedrate, max_feedrates, spm_list):
    """
    Given a set of feedrates and spm values, calculates the homing DDA speed
    We always use the limiting axis' feedrate and SPM
    constant, if applicable.  If there is no limiting axis, we default to
    the first axis' spm value.

    @param int feedrate: The feedrate we want to move at
    @param int list max_feedrates: The max feedrates we will be using
    @param float list spm_list: The steps_per_mm we use to calculate the DDA speed
    @retun float dda_speed: The speed we will be moving at
    """
    if max_feedrates == [] or spm_list == [] or len(spm_list) != len(max_feedrates):
        gcode_error = makerbot_driver.Gcode.CalculateHomingDDAError()
        gcode_error.values['MaxFeedrateLength'] = len(max_feedrates)
        gcode_error.values['SPMLength'] = len(spm_list)
        raise gcode_error
    usable_feedrate = feedrate
    usable_spm = spm_list[0]
    for max_feedrate, spm in zip(max_feedrates, spm_list):
        if usable_feedrate > max_feedrate:
            usable_feedrate = max_feedrate
            usable_spm = spm
    dda_speed = compute_DDA_speed(usable_feedrate, usable_spm)
    return dda_speed
