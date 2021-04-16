import logging

from astroprint.printer.manager import printerManager

class PrintjobSubtopic(object):
	def __init__(self):
		self._logger = logging.getLogger(__name__)

	def start(self, subtopics, payload):
		self._logger.info('Start Print Job: %s', payload)

	def pause(self, subtopics, payload):
		self._logger.info('Pause Print Job')
		printerManager().togglePausePrint()

	def resume(self, subtopics, payload):
		self._logger.info('Resume Print Job')
		printerManager().togglePausePrint()

	def cancel(self, subtopics, payload):
		self._logger.info('Cancel Print Job')
		printerManager().cancelPrint()
