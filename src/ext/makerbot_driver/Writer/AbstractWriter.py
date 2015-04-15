class AbstractWriter(object):

    def __init__(self, file, condition):
        self.external_stop = False
        self._condition = condition
        self.file = file

    def open(self):
        """ Opens the currently set port"""
        raise NotImplementedError()

    def is_open(self):
        """ Fluch of file like objects. """
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def send_action_payload(self, payload):
        """ Send the given payload as an action command

        @param bytearray payload Payload to send as an action payload
        """
        raise NotImplementedError()

    def send_query_payload(self, payload):
        """ Send the given payload as a query command

        @param bytearray payload Payload to send as a query packey
        @return The packet returned by send_command
        """
        raise NotImplementedError()

    def set_external_stop(self, value=True):
        with self._condition:
            self.external_stop = value
