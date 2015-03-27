class S3gStreamError(Exception):
    """
    Raised when unexpected data is found while reading an s3g stream.
    """


class InsufficientDataError(S3gStreamError):
    """
    An insufficientDataError is thrown when there isnt enough data to read in relative to
    a given format string.
    """


class StringTooLongError(S3gStreamError):
    """
    A StringTooLongError is raised when a string being read is longer than the maximum
    payload size
    """


class EndOfFileError(S3gStreamError):
    """
    An EndOfFileError is raised when the end of an s3g file is reached prematurely.
    """


class NotToolActionCmdError(S3gStreamError):
    """
    A NotToolActionCmdError is thrown when an action command is passed in into
    ParseToolAction that is not a tool_action_command
    """


class BadCommandError(S3gStreamError):
    """
    Bad data was found when decoding a command.
    """
    def __init__(self, command):
        self.command = command

    def __str__(self):
        return repr(self.command)


class BadSlaveCommandError(BadCommandError):
    """
    A BadSlaveCommandError is thrown when a slave command is encountered that we
    do not know about
    """


class BadHostCommandError(BadCommandError):
    """
    A BadHostCommandError is thrown when a host command is encountered that we
    do not know about
    """
