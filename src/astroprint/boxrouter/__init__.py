# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

# singleton
_instance = None

def boxrouterManager():
	global _instance
	if _instance is None:
		_instance = AstroprintBoxRouter()
	return _instance

import json
import threading
import logging
import base64
import socket

from time import sleep, time

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from astroprint.network import networkManager
from astroprint.boxrouter.printerlistener import PrinterListener
from astroprint.camera import cameraManager
from astroprint.software import softwareManager
from astroprint.printerprofile import printerProfileManager
from astroprint.printer.manager import printerManager

from ws4py.client.threadedclient import WebSocketClient
from ws4py.messaging import PingControlMessage

LINE_CHECK_STRING = 'box'

class LineCheck(threading.Thread):
	def __init__(self, websocket, timeout=30.0):
		threading.Thread.__init__(self)
		self.websocket = websocket
		self.timeout = timeout
		self.outstandingPings = 0

	def stop(self):
		self.running = False

	def run(self):
		self.running = True
		while self.running:
			sleep(self.timeout)
			if self.websocket.terminated:
				break

			if self.outstandingPings > 0:
				self.websocket._logger.error('The line seems to be down')
				self.websocket.close()
				break
			
			if time() - self.websocket._lastReceived > self.timeout:
				try:
					self.websocket.send(PingControlMessage(data=LINE_CHECK_STRING))
					self.outstandingPings += 1

				except socket.error:
					logger.error("Line Check failed to send")

					#retry connection
					self.websocket.close()

class AstroprintBoxRouterClient(WebSocketClient):
	def __init__(self, hostname, router):
		self._router = router
		self._printerListener = None
		self._lastReceived = 0
		self._subscribers = 0
		self._silentReconnect = False
		self._cameraManager = cameraManager()
		self._profileManager = printerProfileManager()
		self._logger = logging.getLogger(__name__)
		WebSocketClient.__init__(self, hostname)

	def send(self, data):
		try:
			WebSocketClient.send(self, data)

		except socket.error as e:
			self._logger.error('Error raised during send: %s' % e)

			#Something happened to the link. Let's try to reset it
			self.close()

	def ponged(self, pong):
		if self._router._lineCheck and str(pong) == LINE_CHECK_STRING:
			self._router._lineCheck.outstandingPings -= 1

	def closed(self, code, reason=None):
		#only retry if the connection was terminated by the remote or a link check failure (silentReconnect)
		retry = self._router.connected

		self._router.close()

		if retry:
			self._router._doRetry()

	def received_message(self, m):
		self._lastReceived = time()
		msg = json.loads(str(m))
		printer = printerManager()

		if msg['type'] == 'auth':
			self._router.processAuthenticate(msg['data'] if 'data' in msg else None)

		elif msg['type'] == 'set_temp':
			if printer.isOperational():
				payload = msg['payload']
				printer.setTemperature(payload['target'] or 0.0, payload['value'] or 0.0)

		elif msg['type'] == 'update_subscribers':
			self._subscribers += int(msg['data'])

			if not self._printerListener and self._subscribers > 0:
				self.registerEvents()
			elif self._printerListener and self._subscribers <= 0:
				self._subscribers = 0
				self.unregisterEvents()

		elif msg['type'] == 'request':
			try:
				reqId = msg['reqId']
				request = msg['data']['type']
				data = msg['data']['payload']

				if request == 'initial_state':
					response = {
						'printing': printer.isPrinting(),
						'operational': printer.isOperational(),
						'paused': printer.isPaused(),
						'camera': printer.isCameraConnected(),
						'printCapture': self._cameraManager.timelapseInfo,
						'profile': self._profileManager.data
					}
				elif request == 'job_info':
					response = printer._stateMonitor._jobData

				elif request == 'printerCommand':
					command = data['command']
					options = data['options']

					response = {'success': True}
					if command == 'pause' or command == 'resume':
						printer.togglePausePrint();

					elif command == 'cancel':
						printer.cancelPrint();

					elif command == 'photo':
						response['image_data'] = base64.b64encode(self._cameraManager.get_pic())

					else:
						response = {
							'error': True,
							'message': 'Printer command [%s] is not supported' % command
						}

				elif request == 'printCapture':
					freq = data['freq']
					if freq:
						if self._cameraManager.timelapseInfo:
							if self._cameraManager.update_timelapse(freq):
								response = {'success': True}
							else:
								response = {
									'error': True,
									'message': 'Error updating the print capture'
								}
								
						else:
							if self._cameraManager.start_timelapse(freq):
								response = {'success': True}
							else:
								response = {
									'error': True,
									'message': 'Error creating the print capture'
								}

					else:
						response = {
							'error': True,
							'message': 'Frequency required'
						}						

				else:
					response = {
						'error': True,
						'message': 'This Box does not recognize the request type [%s]' % request
					}

				self.send(json.dumps({
					'type': 'req_response',
					'reqId': reqId,
					'data': response
				}))

			except Exception as e:
				message = 'Error sending [%s] response: %s' % (request, e) 
				self._logger.error( message )	
				self.send(json.dumps({
					'type': 'req_response',
					'reqId': reqId,
					'data': {'error': True, 'message':message }
				}))

	def registerEvents(self):
		if not self._printerListener:
			self._printerListener = PrinterListener(self)
			printerManager().registerCallback(self._printerListener)

	def unregisterEvents(self):
		if self._printerListener:
			printerManager().unregisterCallback(self._printerListener)
			self._printerListener.cleanup()
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
		self._lineCheck = None
		self._silentReconnect = False
		self.status = self.STATUS_DISCONNECTED
		self.connected = False

		self._logger.info('This box has id %s' % self.boxId)

		self._eventManager.subscribe(Events.NETWORK_STATUS, self._onNetworkStateChanged)

		self._address = self._settings .get(['cloudSlicer','boxrouter'])

		if self._address:
			self.boxrouter_connect()

		else:
			self._logger.error('cloudSlicer.boxrouter not present in config file')

	@property
	def boxId(self):
		if not self._boxId:
			import os

			boxIdFile = "%s/box-id" % os.path.dirname(self._settings._configfile)

			if os.path.exists(boxIdFile):
				with open(boxIdFile, 'r') as f:
					self._boxId = f.read()

			if not self._boxId:
				import uuid

				self._boxId = uuid.uuid4().hex

				with open(boxIdFile, 'w') as f:
					f.write(self._boxId)

		return self._boxId

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
			self._lineCheck = LineCheck(self._ws)

		except Exception as e:
			self._logger.error("Error connecting to boxrouter: %s" % e)
			self._doRetry(False) #This one should not be silent

		else:
			try:
				self._lineCheck.start()
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

		if self._lineCheck:
			self._lineCheck.stop()

		self._ws = None
		self._listener = None
		self._lineCheck = None

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

	def _doRetry(self, silent=True):
		if self._retries < self.MAX_RETRIES:
			self._retries += 1
			sleep(self.START_WAIT_BETWEEN_RETRIES * self.WAIT_MULTIPLIER_BETWEEN_RETRIES * (self._retries - 1) )
			self._logger.info('Retrying boxrouter connection. Retry #%d' % self._retries)
			self._silentReconnect = silent
			self.boxrouter_connect()

		else:
			self._logger.info('No more retries. Giving up...')
			self.status = self.STATUS_DISCONNECTED
			self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
			self._retries = 0

			#Are we offline?
			nm = networkManager()
			if not nm.checkOnline() and nm.isHotspotActive() is False: #isHotspotActive will return None if not possible
				#get the box hotspot up
				self._logger.info('AstroBox is offline. Starting hotspot...')
				result = nm.startHotspot() 
				if result is True:
					self._logger.info('Hostspot started.')
				else:
					self._logger.error('Failed to start hostspot: %s' % result)

	def processAuthenticate(self, data):
		if data:
			self._silentReconnect = False

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

			sm = softwareManager()

			self._ws.send(json.dumps({
				'type': 'auth',
				'data': {
					'silentReconnect': self._silentReconnect,
					'boxId': self.boxId,
					'variantId': sm.variant['id'],
					'boxName': nm.getHostname(),
					'swVersion': VERSION,
					'platform': sm.platform,
					'localIpAddress': localIpAddress,
					'publicKey': self._publicKey,
					'privateKey': self._privateKey
				}
			}))
