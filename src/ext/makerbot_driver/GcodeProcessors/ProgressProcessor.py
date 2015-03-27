"""
Inserts progress commands in skeinforge gcode
"""
from __future__ import absolute_import

from .Processor import *


class ProgressProcessor(Processor):

    def __init__(self):
        super(ProgressProcessor, self).__init__()
        self.command = re.compile('([A-Z]\d+(\.\d+)? )+')

    @staticmethod
    def create_progress_msg(percent):
        progressmsg = "M73 P%s (progress (%s%%))\n" % (percent, percent)
        return progressmsg

    def process_gcode(self, gcodes, gcode_info, callback=None):

        total_bytes = float(gcode_info['size_in_bytes'])

        current_byte_count = 0
        current_percent = 0
        for code in gcodes:
            current_byte_count += len(code)
            yield code
            new_percent = int(100.0 * (current_byte_count / total_bytes))
            if new_percent > current_percent:
                progressmsg = self.create_progress_msg(new_percent)
                #with self._condition:
                #    self.test_for_external_stop(prelocked=True)
                yield progressmsg
                current_percent = new_percent
                if callback is not None:
                    callback(current_percent)


def main():
    ProgressProcessor().process_gcode(sys.argv[1], sys.argv[2])

if __name__ == "__main__":
    sys.exit(main())
