#end of file tasks for s3g files

import logging
import time
import struct


class FileComplete(object):
    """
    Perform end of file tasks after gcode parsing is complete.
    """

    def finish(self, s3g_file):
        """@param, name of an s3g file to checksum"""
        s_file = open(s3g_file, 'r+b')
        self.finish_fh(s_file)

    def finish_fh(self, s_file):
        """ @param s_file file handle to an s3g file to checksum"""
        checksum = 0

        byte = s_file.read(1)
        while byte:
            data = struct.unpack('>B', byte)
            byte = s_file.read(1)
            # we are using a 2byte checksum
            checksum = (data[0] + checksum) % 65536
        #add checksum to end of file
        s_file.write(bytes(checksum))
