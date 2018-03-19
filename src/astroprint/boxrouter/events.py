# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import json
import logging

from copy import deepcopy

class EventSender(object):
	def __init__(self, router):
		self._logger = logging.getLogger(__name__)
		self._router = router
		self._lastSent = {
			'temp_update': None,
			'status_update': None,
			'printing_progress': None,
			'print_capture': None,
			'print_file_download': None,
			'copy_file_to_home': None
		}

	def sendLastUpdate(self, event):
		if event in self._lastSent:
			self._send(event, self._lastSent[event])

	def sendUpdate(self, event, data):
		if self._lastSent[event] != data and self._send(event, data):
			self._lastSent[event] = deepcopy(data) if data else None

	def _send(self, event, data):
		try:
			self._router.send({
				'type': 'send_event',
				'data': {
					'eventType': event,
					'eventData': data
				}
			})

			return True

		except Exception as e:
			self._logger.error( 'Error sending [%s] event: %s' % (event, e) )
			return False
