# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import json
import logging

from copy import deepcopy

from octoprint.events import eventManager, Events

class PrinterListener(object):
	def __init__(self, socket):
		self._logger = logging.getLogger(__name__)
		self._socket = socket
		self._lastSent = {
			'temp_update': None,
			'status_update': None,
			'printing_progress': None,
			'print_capture': None,
			'print_file_download': None
		}

		em = eventManager()

		#register for print_capture events
		em.subscribe(Events.CAPTURE_INFO_CHANGED, self._onCaptureInfoChanged)
		em.subscribe(Events.CLOUD_DOWNLOAD, self._onDownload)

	def __del__(self):
		self.cleanup()

	def cleanup(self):
		em = eventManager()

		em.unsubscribe(Events.CAPTURE_INFO_CHANGED, self._onCaptureInfoChanged)
		em.unsubscribe(Events.CLOUD_DOWNLOAD, self._onDownload)

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
			'camera': flags['camera']
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

	def _onCaptureInfoChanged(self, event, payload):
		self._sendUpdate('print_capture', payload)

	def _onDownload(self, event, payload):
		data = {
			'id': payload['id'],
			'selected': False
		}

		if payload['type'] == 'error':
			data['error'] = True
			data['message'] = payload['reason'] if 'reason' in payload else 'Problem downloading'

		elif payload['type'] == 'cancelled':
			data['cancelled'] = True

		else:
			data['progress'] = 100 if payload['type'] == 'success' else payload['progress']

		self._sendUpdate('print_file_download', data)

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

				self._lastSent[event] = deepcopy(data) if data else None

			except Exception as e:
				self._logger.error( 'Error sending [%s] event: %s' % (event, e) )		
