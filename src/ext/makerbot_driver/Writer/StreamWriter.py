""" An implementation of S3g that sends s3g packets to a stream.
"""
from __future__ import absolute_import

import time
import logging

from . import AbstractWriter
import makerbot_driver


class StreamWriter(AbstractWriter):
    """ Represents a writer to a data stream, usually a tty or USB connection
    to a bot at the end of a wire.
    """

    def __init__(self, file, condition):
        """ Initialize a new StreamWriter object

        @param string file File object to interact with
        """
        super(StreamWriter, self).__init__(file, condition)
        self._serialLogger = logging.getLogger('SERIAL')
        self._serialLogEnabled =  self._serialLogger.isEnabledFor(logging.DEBUG)
        self._serialLogEnabled and self._serialLogger.debug('{"event":"begin_writing_to_stream", "stream":%s}', str(self.file))
        self.total_retries = 0
        self.total_overflows = 0

    # TODO: test me
    def send_query_payload(self, payload):
        return self.send_command(payload)

    # TODO: test me
    def send_action_payload(self, payload):
        self.send_command(payload)

    def close(self):
        with self._condition:
            if self.is_open() and self.file is not None:
                self.file.close()

    def open(self):
        """ Open or re-open an already defined stream connection """
        with self._condition:
            if self.file is not None:
                self.file.open()

    def is_open(self):
        """@returns true if a port is open and active, False otherwise """
        return_val = False
        if self.file is not None:
            return_val = self.file.isOpen()
        return return_val

    def send_command(self, payload):
        packet = makerbot_driver.Encoder.encode_payload(payload)
        return self.send_packet(packet)

    def send_packet(self, packet):
        """
        Attempt to send a packet to the machine, retrying up to 5 times if an error
        occurs.
        @param packet Packet to send to the machine
        @return Response payload, if successful.
        """
        overflow_count = 0
        retry_count = 0
        received_errors = []
        with self._condition:

            while True:
                if self.external_stop:
                    self._serialLogEnabled and self._serialLogger.error('{"event":"external_stop"}')
                    raise makerbot_driver.ExternalStopError
                decoder = makerbot_driver.Encoder.PacketStreamDecoder()
                self.file.write(packet)
                self.file.flush()

                self._serialLogEnabled and self._serialLogger.info('{"event":"packet_sent", "data": "%s"}' % ' '.join('0x{:02x}'.format(x) for x in packet) )

                # Timeout if a response is not received within 1 second.
                start_time = time.time()

                try:
                    while (decoder.state != 'PAYLOAD_READY'):
                        # Try to read a byte
                        data = ''
                        while data == '':
                            if (time.time() > start_time + makerbot_driver.timeout_length):
                                self._serialLogEnabled and self._serialLogger.error('{"event":"machine_timeout"}')
                                raise makerbot_driver.TimeoutError(len(data), decoder.state)

                            # pySerial streams handle blocking read. Be sure to set up a timeout when
                            # initializing them, or this could hang forever
                            data = self.file.read(1)

                        data = ord(data)
                        #self._serialLogEnabled and self._serialLogger.info("byte read: 0x%x" % data)
                        decoder.parse_byte(data)

                    self._serialLogEnabled and self._serialLogger.info('{"event":"response_received", "data": "%s"}' % ' '.join('0x{:02x}'.format(x) for x in decoder.payload) )
                    makerbot_driver.Encoder.check_response_code(decoder.payload[0])
                    if self.external_stop:
                        self._serialLogEnabled and self._serialLogger.error('{"event":"external_stop"}')
                        raise makerbot_driver.ExternalStopError

                    # TODO: Should we chop the response code?
                    return decoder.payload

                except (makerbot_driver.BufferOverflowError) as e:
                    # Relative to the StreamWriter, BufferOverflowErrors aren't retryable.  But, they
                    # are expected to be caught by a higher power

                    self._serialLogEnabled and self._serialLogger.debug('{"event":"buffer_overflow", "overflow_count":%i, "retry_count"=%i}', overflow_count, retry_count)

                    self.total_overflows += 1
                    overflow_count += 1
                    raise e

                except makerbot_driver.RetryableError as e:
                    # Sent a packet to the host, but got a malformed response or timed out waiting
                    # for a reply. Retry immediately.

                    self._serialLogEnabled and self._serialLogger.debug('{"event":"transmission_problem", "exception":"%s", "message":"%s", "retry_count"=%i}', type(e), e.__str__(), retry_count)

                    self.total_retries += 1
                    retry_count += 1
                    received_errors.append(e.__class__.__name__)

                    #flush the input buffer
                    self.file.flushInput()

                except Exception as e:
                    # Other exceptions are propigated upwards.

                    self._serialLogEnabled and self._serialLogger.error('{"event":"unhandled_exception", "exception":"%s", "message":"%s", "retry_count"=%i}', type(e), e.__str__(), retry_count)
                    raise e

                if retry_count >= makerbot_driver.max_retry_count:
                    self._serialLogEnabled and self._serialLogger.error('{"event":"transmission_error"}')
                    raise makerbot_driver.TransmissionError(received_errors)
