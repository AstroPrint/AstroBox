class NonBinaryModeFileError(IOError):
    """
    A NonBinaryModeFileError is raised when a file is
    passed into FileWriter that is not opened in
    binary mode.  Open a binary mode file with 'wb'
    """
