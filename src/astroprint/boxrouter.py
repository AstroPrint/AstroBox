# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import json
import socket
import asynchat
import asyncore
import threading
import logging

from time import sleep
from octoprint.events import eventManager, Events

from octoprint.settings import settings

# singleton
_instance = None

def boxrouterManager():
	global _instance
	if _instance is None:
		_instance = AstroprintBoxRouter()
	return _instance

class AstroprintBoxRouter(asynchat.async_chat):
	MAX_RETRIES = 5
	WAIT_BETWEEN_RETRIES = 5 #seconds

	STATUS_DISCONNECTED = 'disconnected'
	STATUS_CONNECTING = 'connecting'
	STATUS_CONNECTED = 'connected'
	STATUS_ERROR = 'error'

	def __init__(self):
		asynchat.async_chat.__init__(self)
		self._ibuffer = []
		self.set_terminator("\n")
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self._eventManager = eventManager()
		self._retries = 0
		self.status = self.STATUS_DISCONNECTED
		self.connected = False

		addr = self._settings .get(['cloudSlicer','boxrouter'])

		if addr:
			if ":" in addr:
				addr = addr.split(':')
				self._address = addr[0]
				self._port = int(addr[1])
			else:
				self._address = addr
				self._port = 80

			self.boxrouter_connect()

		else:
			self._logger.error('boxrouter address not specified in config')

	def boxrouter_disconnect(self):
		self.close()

	def close(self):
		self.connected = False
		self._publicKey = None
		self._privateKey = None
		self.status = self.STATUS_DISCONNECTED
		self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
		asynchat.async_chat.close(self)
		self._listener.join()
		self._listener = None

	def boxrouter_connect(self):
		self._publicKey	= self._settings.get(['cloudSlicer', 'publicKey'])
		self._privateKey = self._settings.get(['cloudSlicer', 'privateKey'])

		if self._publicKey and self._privateKey:
			try:
				self.status = self.STATUS_CONNECTING
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
				self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
				self.connect( (self._address, self._port) )

			except Exception as e:
				self._logger.error(e)

			self._listener = threading.Thread(target=asyncore.loop)
			self._listener.start()

	def handle_error(self):
		self.status = self.STATUS_ERROR
		self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
		self._logger.error('Unkonwn error connecting to the AstroPrint service')
		self.connected = False
		self.close()
		self._doRetry()

	def handle_close(self):
		self.close()
		self._doRetry()

	def collect_incoming_data(self, data):
		self._ibuffer.append(data)

	def found_terminator(self):
		self.onMessage()
		self._ibuffer = []

	def _doRetry(self):
		if self._retries < self.MAX_RETRIES:
			self._retries += 1
			self._logger.info('Retrying boxrouter connection. Retry #%d' % self._retries)
			sleep(self.WAIT_BETWEEN_RETRIES)
			self.boxrouter_connect()
		else:
			self._logger.info('No more retries. Giving up...')

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
				self.status = self.STATUS_ERROR
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);

			elif 'success' in data:
				self._logger.info("Connected to astroprint service")
				self.connected = True;
				self._retries = 0;
				self.status = self.STATUS_CONNECTED
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);

		else:
			from octoprint.server import VERSION, networkManager

			self.push(json.dumps({
				'type': 'auth',
				'data': {
					'boxId': networkManager.getMacAddress(),
					'boxName': networkManager.getHostname(),
					'swVersion': VERSION,
					'publicKey': self._publicKey,
					'privateKey': self._privateKey
				}
			}))