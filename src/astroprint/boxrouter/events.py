# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import json
import logging

from copy import deepcopy

from octoprint.events import eventManager, Events

class EventSender(object):
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

	def _onCaptureInfoChanged(self, event, payload):
		self.sendUpdate('print_capture', payload)

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

		self.sendUpdate('print_file_download', data)

	def sendLastUpdate(self, event):
		if event in self._lastSent:
			self._send(event, self._lastSent[event])

	def sendUpdate(self, event, data):
		if self._lastSent[event] != data and self._send(event, data):
			self._lastSent[event] = deepcopy(data) if data else None

	def _send(self, event, data):
		try:
			self._socket.send(json.dumps({
				'type': 'send_event',
				'data': {
					'eventType': event,
					'eventData': data
				}
			}))

			return True

		except Exception as e:
			self._logger.error( 'Error sending [%s] event: %s' % (event, e) )
			return False
