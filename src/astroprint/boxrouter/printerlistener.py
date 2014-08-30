# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import json
import logging

class PrinterListener(object):
	def __init__(self, socket):
		self._logger = logging.getLogger(__name__)
		self._socket = socket
		self._lastSent = {
			'temp_update': None,
			'status_update': None,
			'printing_progress': None
		}

	def sendHistoryData(self, data):
		pass

	def addTemperature(self, data):		
		payload = {
			'bed': { 'actual': data['bed']['actual'], 'target': data['bed']['target'] },
			'tool0': { 'actual': data['tool0']['actual'], 'target': data['tool0']['target'] }
		}

		self._sendUpdate('temp_update', payload)

	def addLog(self, data):
		pass

	def addMessage(self, data):
		pass

	def sendCurrentData(self, data):
		flags = data['state']['flags']

		payload = {
			'operational': flags['operational'],
			'printing': flags['printing'] or flags['paused'],
			'paused': flags['paused'],
		}

		self._sendUpdate('status_update', payload)

		if payload['printing']:
			self._sendUpdate('printing_progress', data['progress'])

		elif self._lastSent['printing_progress']:
			self._sendUpdate('printing_progress', None)

	def sendEvent(self, type):
		pass

	def sendFeedbackCommandOutput(self, name, output):
		pass

	def _sendUpdate(self, event, data):
		if self._lastSent[event] != data:
			try:
				self._socket.send(json.dumps({
					'type': 'send_event',
					'data': {
						'eventType': event,
						'eventData': data
					}
				}))

				self._lastSent[event] = data

			except Exception as e:
				self._logger.error( 'Error sending [%s] event: %s' % (event, e) )		
