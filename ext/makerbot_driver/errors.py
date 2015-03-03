from constants import *


class RetryableError(Exception):
    """
    RetryableError is a generic error that other errors inherit from.  An error is considered
    retryable if it does not cause the state machine to halt.
    """


class PacketDecodeError(RetryableError):
    """
    Error that occured when evaluating a packet. These errors are caused by problems that
    are potentially recoverable.
    """
    def __init__(self, actual, expected):
        self.value = {
            'ExpectedValue': expected,
            'ActualValue': actual,
        }

    def __str__(self):
        return str(self.value)


class PacketLengthError(PacketDecodeError):
    """
    Signifies an error in the length of a packet
    """


class PacketLengthFieldError(PacketDecodeError):
    """
    Signifies an error in a specific field of the packet (i.e. the payload isnt the correct length
    """


class PacketHeaderError(PacketDecodeError):
    """
    Signifies an incorrect header on a packet
    """


class PacketCRCError(PacketDecodeError):
    """
    Signifies a mismatch in expected and actual CRCs
    """


class GenericError(RetryableError):
    """
    A generic error reported by the bot
    """


class CRCMismatchError(RetryableError):
    """
    Signifies a bad crc code was received by the machine
    """

class PacketTimeoutError(RetryableError):
    """
    Packet timeout error, packet discarded
    """


class TimeoutError(RetryableError):
    """
    Signifies that a packet has taken too long to be received
    """
    def __init__(self, data_length, decoder_state):
        self.data_length = data_length
        self.decoder_state = decoder_state
        self.value = {
            'DATA LENGTH': self.data_length,
            'DECODER STATE': self.decoder_state
        }


class BufferOverflowError(Exception):
    """
    Signifies a reported overflow of the buffer from the bot
    """

class PacketTooBigError(Exception):
    """
    Action buffer overflow, entire packet discarded
    """


class BuildCancelledError(Exception):
    """
    Signifies the cancellation of a build.  This is ALSO
    not mispelled, its just the British way of spelling
    Cancelled.
    """


class ActiveBuildError(Exception):
    """
    Signigifies a report that the the bot is actively building from a local source
    """


class OverheatError(Exception):
    """
    Signifies that the bot is reporting and overheat state and can no longer accept commands
    """


class CommandNotSupportedError(Exception):
    """
    Signifies that the bot reported receiving a command it does not support
    """


class TransmissionError(IOError):
    """
    A transmission error is raised when the s3g driver encounters
    too many errors while communicating, OR the machine encountering
    errors when communicating with its tools. This error is non-recoverable
    without resetting the state of the machine.
    """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)  # This returns a str of the value because
                                  #TransmissionErrors can contain
                                  #a list of proximate errors that caused this


class ToolBusError(IOError):
    """
    A toolbus error signifies a transmission error between the machine and its
    toolbus.
    """


class DownstreamTimeoutError(ToolBusError):
    """
    Signifiees the machine cannot communicate with the tool
    due to a communication timeout.
    """


class ToolLockError(ToolBusError):
    """
    Signifies the machine cannot communicate with the tool
    due to the tool being locked
    """


class ExtendedStopError(Exception):
    """
    An extended stop error is thrown if there was a problem executing an extended stop on the machine.
    """


class SDCardError(Exception):
    """
    An SD card error is thrown if there was a problem accessing the SD card. This should be recoverable,
    if the user replaces or reseats the SD card.
    """
    def __init__(self, response_code):
        self.response_code = response_code
        self.response_code_string = 'RESPONSE_CODE_NOT_RECOGNIZED'
        #Do a reverse lookup
        for key, val in sd_error_dict.items():
            if val == response_code:
                self.response_code_string = key
                break

    def __str__(self):
        return self.response_code_string


class ProtocolError(Exception):
    """
    A protocol error is caused when a machine provides a valid response packet with an invalid
    response (for example, too many or two few resposne variables). It means that the machine is not
    implementing the protocol correctly.
    """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class HeatElementReadyError(ProtocolError):
    """
    A heat element ready error is raised when a non 1 or 0 value is returned
    """


class EEPROMMismatchError(ProtocolError):
    """An EEPROM mismatch error is raised when the length of the information written to the eeprom doesnt match the length of the information passed into write_to_EEPROM
    """


class UnknownResponseError(ProtocolError):
    """
    An UnknownResponseError is thrown the machine responds with a value
    that is not known to s3g.
    """


class ParameterError(ValueError):
    """
    A parameter error is thrown when an incorrect parameter is passed into an s3g function (i.e. incorrect button name, etc)
    """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class ButtonError(ParameterError):
    """
    A bad button error is raised when a button that is not of type up, down, left, right or center is passed into wait_for_button
    """


class EEPROMLengthError(ParameterError):
    """
    An EEPROM length error is raised when too much information is either read or written to the EEPROM
    """


class ToolIndexError(ParameterError):
    """
    A tool index error is called when a tool index is passed in that is either < 0 or > 127
    """


class PointLengthError(ParameterError):
    """
    A point length error is caused when a point's length is either too long or too short.
    """


class RecipeNotFoundError(KeyError):
    """
    A Recipe not found error is thrown when the Gcode Assembler tries to find a specific recipe, but fails.
    """


class ExternalStopError(Exception):
    """
    An ExternalStopError is thrown when an external
    source wishes to force the StreamWriter to stop
    sending packets to a stream.
    """
