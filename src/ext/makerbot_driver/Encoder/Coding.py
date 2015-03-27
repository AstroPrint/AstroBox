from __future__ import absolute_import

import struct
import array

import makerbot_driver


def decode_bitfield(number):
    """
    Given an uint8 number, returns its decoded bitfield

    @param int number:  A number to be decoded
    @return list bitfield: The decoded bitfield
    """
    if number < 0 or number > 255:
        raise ValueError
    bitfield = []
    for i in range(8):
        bitfield.append(1 == (number >> i) & 0x01)
    return bitfield


def encode_int32(number):
    """
    Encode a 32-bit signed integer as a 4-byte string
    @param number
    @return byte array of size 4 that represents the integer
    """
    return struct.pack('<i', number)


def encode_uint32(number):
    """
    Encode a 32-bit unsigned integer as a 4-byte string
    @param number
    @return byte array of size 4 that represents the integer
    """
    return struct.pack('<I', number)


def decode_int32(data):
    """
    Decode a 4-byte string into a 32-bit signed integer
    @param data: byte array of size 4 that represents the integer
    @param return: decoded integer
    """
    if isinstance(data, bytearray):
        data = array.array('B', data)
    return struct.unpack('<i', data)[0]


def encode_int16(number):
    """
    Encode a 16-bit signed integer as a 2-byte string
    @param number
    @return byte array of size 2 that represents the integer
    """
    return struct.pack('<h', number)


def encode_uint16(number):
    """
    Encode a 16-bit unsigned integer as a 2-byte string
    @param number
    @return byte array of size 2 that represents the integer
    """
    return struct.pack('<H', number)


def decode_uint16(data):
    """
    Decode a 2-byte string as a 16-bit integer
    @param data byte array of size 2 that represents the integer
    @return decoded integer
    """
    #Byte arrays need to be converted into arrays to be unpackable by struct
    if isinstance(data, bytearray):
        data = array.array('B', data)
    return struct.unpack('<H', data)[0]


def encode_axis(axis):
    """
    Encode an array of axes names into an axis bitfield
    @param axes Array of axis names ['x', 'y', ...]
    @return bitfield containing a representation of the axes map
    """
    axes_map = {
        'x': 0x01,
        'y': 0x02,
        'z': 0x03,
        'a': 0x04,
        'b': 0x05,
    }

    return axes_map[axis.lower()]


def encode_axes(axes):
    """
    Encode an array of axes names into an axis bitfield
    @param axes Array of axis names ['x', 'y', ...]
    @return bitfield containing a representation of the axes map
    """
    axes_map = {
        'x': 0x01,
        'y': 0x02,
        'z': 0x04,
        'a': 0x08,
        'b': 0x10,
    }

    bitfield = 0

    for axis in axes:
        bitfield |= axes_map[axis.lower()]

    return bitfield


def unpack_response(format, data):
    """
    Attempt to unpack the given data using the specified format. Throws a protocol
    error if the unpacking fails.

    @param format Format string to use for unpacking
    @param data Data to unpack.  We _cannot_ unpack strings!
    @return list of values unpacked, if successful.
    """

    try:
        return struct.unpack(format, buffer(data))
    except struct.error as e:
        raise makerbot_driver.errors.ProtocolError("Unexpected data returned from machine. Expected length=%i, got=%i, error=%s" %
                                   (struct.calcsize(format), len(data), str(e)))


def unpack_response_with_string(format, data):
    """
    Attempt to unpack the given data using the specified format, and with a trailing,
    null-terminated string. Throws a protocol error if the unpacking fails.

    @param format Format string to use for unpacking
    @param data Data to unpack, including a string if specified
    @return list of values unpacked, if successful.
    """
    #The +1 is for the null terminator of the string
    if (len(data) < struct.calcsize(format) + 1):
        raise makerbot_driver.errors.ProtocolError("Not enough data received from machine, expected=%i, got=%i" %
                                   (struct.calcsize(format) + 1, len(data)))

    #Check for a null terminator on the string
    elif (data[-1]) != 0:
        raise makerbot_driver.errors.ProtocolError("Expected null terminated string.")

    output = unpack_response(format, data[0:struct.calcsize(format)])
    output += data[struct.calcsize(format):],
    return output
