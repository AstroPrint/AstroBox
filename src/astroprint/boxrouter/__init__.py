# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import json
import threading
import logging

from time import sleep

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from astroprint.network import networkManager
from astroprint.boxrouter.printerlistener import PrinterListener

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
		#it needs to be imported here because on the main body 'printer' is None
		from octoprint.server import printer

		self._router = router
		self._printer = printer
		self._printerListener = None
		self._subscribers = 0
		WebSocketClient.__init__(self, hostname)

	def closed(self, code, reason=None):
		#only retry if the connection was terminated by the remote
		retry = self._router.connected

		self._router.close()

		if retry:
			self._router._doRetry()

	def received_message(self, m):
		msg = json.loads(str(m))

		if msg['type'] == 'auth':
			self._router.processAuthenticate(msg['data'] if 'data' in msg else None)

		elif msg['type'] == 'set_temp':
			if self._printer.isOperational():
				payload = msg['payload']
				self._printer.setTemperature(payload['target'] or 0.0, payload['value'] or 0.0)

		elif msg['type'] == 'update_subscribers':
			self._subscribers += int(msg['data'])

			if not self._printerListener and self._subscribers > 0:
				self.registerEvents()
			elif self._printerListener and self._subscribers <= 0:
				self._subscribers = 0
				self.unregisterEvents()

		elif msg['type'] == 'request':
			reqId = msg['reqId']
			request = msg['data']['type']
			data = msg['data']['payload']

			if request == 'initial_state':
				response = {
					'printing': self._printer.isPrinting(),
					'operational': self._printer.isOperational(),
					'paused': self._printer.isPaused()
				}
			elif request == 'job_info':
				response = self._printer._stateMonitor._jobData

			elif request == 'printerCommand':
				command = data['command']
				options = data['options']

				response = {'success': True}
				if command == 'pause' or command == 'resume':
					self._printer.togglePausePrint();

				elif command == 'cancel':
					self._printer.cancelPrint();

				else:
					response = {
						'error': True,
						'message': 'Printer command [%s] is not supported' % command
					}

			else:
				response = {
					'error': True,
					'message': 'This Box does not recognize the request type [%s]' % request
				}

			try:
				self.send(json.dumps({
					'type': 'req_response',
					'reqId': reqId,
					'data': response
				}))

			except Exception as e:
				self._logger.error( 'Error sending [%s] response: %s' % (request, e) )	

	def registerEvents(self):
		if not self._printerListener:
			self._printerListener = PrinterListener(self)
			self._printer.registerCallback(self._printerListener)

	def unregisterEvents(self):
		if self._printerListener:
			self._printer.unregisterCallback(self._printerListener)
			self._printerListener = None


class AstroprintBoxRouter(object):
	MAX_RETRIES = 5
	START_WAIT_BETWEEN_RETRIES = 5 #seconds
	WAIT_MULTIPLIER_BETWEEN_RETRIES = 2

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
		self._boxId = None
		self._ws = None
		self.status = self.STATUS_DISCONNECTED
		self.connected = False


		self._eventManager.subscribe(Events.NETWORK_STATUS, self._onNetworkStateChanged)

		self._address = self._settings .get(['cloudSlicer','boxrouter'])

		if self._address:
			self.boxrouter_connect()

		else:
			self._logger.error('cloudSlicer.boxrouter not present in config file')

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
			self._ws = AstroprintBoxRouterClient(self._address, self)
			self._ws.connect()

		except Exception as e:
			self._logger.error("Error connecting to boxrouter: %s" % e)
			self._doRetry()

		else:
			try:
				self._ws.run_forever()

			except Exception as e:
				self._error(e)

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
			self._ws.unregisterEvents()

		self._ws = None
		self._listener = None

	def _onNetworkStateChanged(self, event, state):
		if state == 'offline':
			if self.connected:
				self._logger.info('Device is offline. Closing box router socket.')
				self.boxrouter_disconnect()

		elif state == 'online':
			if not self.connected:
				self.boxrouter_connect()

		else:
			self._logger.warn('Invalid network state (%s)' % state)

	def _error(self, err):
		self._logger.error('Unkonwn error in the connection with AstroPrint service: %s' % err)
		self.status = self.STATUS_ERROR
		self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
		self.close()
		self._doRetry()

	def _doRetry(self):
		if self._retries < self.MAX_RETRIES:
			self._retries += 1
			sleep(self.START_WAIT_BETWEEN_RETRIES * self.WAIT_MULTIPLIER_BETWEEN_RETRIES * (self._retries - 1) )
			self._logger.info('Retrying boxrouter connection. Retry #%d' % self._retries)
			self.boxrouter_connect()

		else:
			self._logger.info('No more retries. Giving up...')
			self.status = self.STATUS_DISCONNECTED
			self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
			self._retries = 0

			#Are we offline?
			nm = networkManager()
			if not nm.checkOnline() and nm.isHotspotActive() == False:
				#get the box hotspot up
				self._logger.info('AstroBox is offline. Starting hotspot...')
				result = nm.startHotspot() 
				if result is True:
					self._logger.info('Hostspot started.')
				else:
					self._logger.error('Failed to start hostspot: %s' % result)

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
			from octoprint.server import VERSION

			nm = networkManager()

			activeConnections = nm.getActiveConnections()

			if activeConnections and ( activeConnections['wired'] or activeConnections['wireless']):
				preferredConn = activeConnections['wired'] or activeConnections['wireless']
				localIpAddress = preferredConn['ip']
			else:
				localIpAddress = None

			if not self._boxId:
				import os

				boxIdFile = "%s/box-id" % os.path.dirname(self._settings._configfile)

				if os.path.exists(boxIdFile):
					with open(boxIdFile, 'r') as f:
						self._boxId = f.read()

				else:
					import uuid

					self._boxId = uuid.uuid4().hex

					with open(boxIdFile, 'w') as f:
						f.write(self._boxId)

			self._ws.send(json.dumps({
				'type': 'auth',
				'data': {
					'boxId': self._boxId,
					'boxName': nm.getHostname(),
					'swVersion': VERSION,
					'localIpAddress': localIpAddress,
					'publicKey': self._publicKey,
					'privateKey': self._privateKey
				}
			}))
