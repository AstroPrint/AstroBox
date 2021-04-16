import logging

from .subtopics.printjob import PrintjobSubtopic

class MQTTTopics(object):
	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._printjob = None

	def printjob(self, subtopic, payload):
		if self._printjob is None:
			self._printjob = PrintjobSubtopic()

		self._executeSubtopicInClass(self._printjob, subtopic, payload)

	def _executeSubtopicInClass(self, claz, subtopic, payload):
		if subtopic:
			subtopic = subtopic[1:]
			subtopics = subtopic.split('/')

			try:
				func = getattr(claz, subtopics[0])
				func(subtopics[1:], payload)

			except AttributeError:
				self._logger.warn('Invalid subtopic: %s', subtopic)

		else:
			self._logger.error('No subtopic')
