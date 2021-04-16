import re
import json

from octoprint.events import eventManager, Events

class SystemListener(object):
	_tempKeyRegex = re.compile(r'^(tool[\d+]|bed)$')

	def __init__(self, mqttClient):
		self._mqttClient = mqttClient
		self._lastEvent = {}
		em = eventManager()

		#register for system events
		em.subscribe(Events.TEMPERATURE_CHANGE, self._onTempChange)

	def cleanup(self):
		em = eventManager()

		em.unsubscribe(Events.TEMPERATURE_CHANGE, self._onTempChange)
		self._mqttClient = None
		self._lastEvent = {}

	def _publishIfChanged(self, topic, data):
		publish = False

		if topic not in self._lastEvent:
			self._lastEvent[topic] = data
			publish = True
		elif self._lastEvent[topic] != data:
			self._lastEvent[topic] = data
			publish = True

		if publish:
			self._mqttClient.publish(topic, data)

	def _onTempChange(self, event, data):
		for k in data:
			if self._tempKeyRegex.match(k):
				self._publishIfChanged('sensors/temp/%s' % k, json.dumps(data[k]))
