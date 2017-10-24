# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

class PrinterListener(object):
	def __init__(self, socket):
		self._socket = socket

	def sendHistoryData(self, data):
		pass

	def addTemperature(self, data):
		payload = {}

		if 'bed' in data:
			payload['bed'] = { 'actual': data['bed']['actual'], 'target': data['bed']['target'] }

		if data:
			for key in sorted(data.keys()):
				if key == 'bed' or key[:4] == 'tool':
					payload[key] = data[key]

		self._socket.broadcastEvent('temp_update', payload)

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
			'camera': flags['camera'],
			'heatingUp': flags['heatingUp'],
			'state': data['state']['text'].lower(),
			'tool': data['tool']
		}

		self._socket.broadcastEvent('status_update', payload)

		if payload['printing']:
			self._socket.broadcastEvent('printing_progress', data['progress'])

		else:
			self._socket.broadcastEvent('printing_progress', None)

	def sendEvent(self, type):
		pass

	def sendFeedbackCommandOutput(self, name, output):
		pass
