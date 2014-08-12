# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import json
import socket
import asynchat
import asyncore
import threading
import logging

from octoprint.settings import settings

class AstroprintBoxRouter(asynchat.async_chat):
	def __init__(self):
		asynchat.async_chat.__init__(self)
		self._ibuffer = []
		self.set_terminator("\n")
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self.connected = False

		addr = self._settings .get(['cloudSlicer','boxrouter'])

		if ":" in addr:
			addr = addr.split(':')
			self._address = addr[0]
			self._port = int(addr[1])
		else:
			self._address = addr
			self._port = 80

		self.boxrouter_connect()

		self._listener = threading.Thread(target=asyncore.loop)
		self._listener.daemon = True
		self._listener.start()

	def boxrouter_connect(self):
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect( (self._address, self._port) )

	#def handle_error(self):
	#	self._logger.error('Unable to connect to the astroprint service')

	def handle_connect(self):
		pass

	def handle_close(self):
		print 'remote closed'
		self.close()
		self.connected = False

	def collect_incoming_data(self, data):
		self._ibuffer.append(data)

	def found_terminator(self):
		self.onMessage()
		self._ibuffer = []

	def onMessage(self):
		for msg in self._ibuffer:
			msg = json.loads(msg)

			self._logger.info("Received message: %s" % msg)

			if msg['type'] == 'auth':
				self.processAuthenticate(msg['data'] if 'data' in msg else None)

	def processAuthenticate(self, data):
		if data:
			if 'error' in data:
				self._logger.warn(data['message'] if 'message' in data else 'Unkonwn authentication error')
			elif 'success' in data:
				self._logger.info("Connected to astroprint service")
				self.connected = True;

		else:
			from octoprint.server import VERSION, networkManager

			self.push(json.dumps({
				'type': 'auth',
				'data': {
					'boxId': '12345',
					'boxName': networkManager.getHostname(),
					'swVersion': VERSION,
					'publicKey': self._settings.get(['cloudSlicer', 'publicKey']),
					'privateKey': self._settings .get(['cloudSlicer', 'privateKey'])
				}
			}))