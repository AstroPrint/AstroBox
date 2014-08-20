# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import json
import threading
import logging

from time import sleep
from octoprint.events import eventManager, Events

from octoprint.settings import settings

from ws4py.client.threadedclient import WebSocketClient

# singleton
_instance = None

def boxrouterManager():
	global _instance
	if _instance is None:
		_instance = AstroprintBoxRouter()
	return _instance

class AstroprintBoxRouterClient(WebSocketClient):
	def __init__(self, hostname, router):
		self._router = router
		WebSocketClient.__init__(self, hostname)

	def closed(self, code, reason=None):
		self._router.close()
		self._router._doRetry()

	def received_message(self, m):
		msg = json.loads(str(m))

		if msg['type'] == 'auth':
			self._router.processAuthenticate(msg['data'] if 'data' in msg else None)

class AstroprintBoxRouter(object):
	MAX_RETRIES = 5
	WAIT_BETWEEN_RETRIES = 5 #seconds

	STATUS_DISCONNECTED = 'disconnected'
	STATUS_CONNECTING = 'connecting'
	STATUS_CONNECTED = 'connected'
	STATUS_ERROR = 'error'

	def __init__(self):
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self._eventManager = eventManager()
		self._retries = 0
		self._listener = None
		self._ws = None
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

	def boxrouter_connect(self):
		if not self.connected:
			self._publicKey	= self._settings.get(['cloudSlicer', 'publicKey'])
			self._privateKey = self._settings.get(['cloudSlicer', 'privateKey'])

			if self._publicKey and self._privateKey:
				self.status = self.STATUS_CONNECTING
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);

				self._listener = threading.Thread(target=self.run_threaded)
				self._listener.daemon = True
				self._listener.start()

	def run_threaded(self):
		try:
			self._ws = AstroprintBoxRouterClient('ws://%s:%d/' % (self._address, self._port), self)
			self._ws.connect()

		except Exception as e:
			self._logger.error("Error connecting to boxrouter: %s" % e)
			self._doRetry()

		else:
			try:
				self._ws.run_forever()

			except:
				self._error()

	def boxrouter_disconnect(self):
		if self.connected:
			self.close()

	def close(self):
		self.connected = False
		self._publicKey = None
		self._privateKey = None
		self.status = self.STATUS_DISCONNECTED
		self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);

		if self._ws:
			self._ws.close()

		self._ws = None
		self._listener = None

	def _error(self):
		self.status = self.STATUS_ERROR
		self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
		self._logger.error('Unkonwn error connecting to the AstroPrint service')
		self.close()
		self._doRetry()

	def _doRetry(self):
		if self._retries < self.MAX_RETRIES:
			self._retries += 1
			self._logger.info('Retrying boxrouter connection. Retry #%d' % self._retries)
			sleep(self.WAIT_BETWEEN_RETRIES)
			self.boxrouter_connect()

		else:
			self._logger.info('No more retries. Giving up...')
			self.status = self.STATUS_DISCONNECTED
			self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);

	def processAuthenticate(self, data):
		if data:
			if 'error' in data:
				self._logger.warn(data['message'] if 'message' in data else 'Unkonwn authentication error')
				self.status = self.STATUS_ERROR
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
				self.close()

			elif 'success' in data:
				self._logger.info("Connected to astroprint service")
				self.connected = True;
				self._retries = 0;
				self.status = self.STATUS_CONNECTED
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);

		else:
			from octoprint.server import VERSION, networkManager

			self._ws.send(json.dumps({
				'type': 'auth',
				'data': {
					'boxId': networkManager.getMacAddress(),
					'boxName': networkManager.getHostname(),
					'swVersion': VERSION,
					'publicKey': self._publicKey,
					'privateKey': self._privateKey
				}
			}))
