# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016-2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import threading

# singleton
_instance = None
creationLock = threading.Lock()

def boxrouterManager():
	global _instance

	if _instance is None:
		with creationLock:
			#check again because maybe another lock created it
			if _instance is None:
				_instance = AstroprintBoxRouter()

	return _instance

import json
import threading
import logging
import socket
import os
import weakref
import uuid
import sys

from time import sleep, time
from flask_login import current_user
from ws4py.client.threadedclient import WebSocketClient
from ws4py.messaging import PingControlMessage

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from astroprint.network.manager import networkManager
from astroprint.software import softwareManager
from astroprint.printer.manager import printerManager

from .handlers import BoxRouterMessageHandler
from .systemlistener import SystemListener
from .events import EventSender

LINE_CHECK_STRING = 'box'

class AstroprintBoxRouterClient(WebSocketClient):
	def __init__(self, hostname, router):
		self._systemListener = None
		self._lastReceived = 0
		self._lineCheck = None
		self._error = False

		self._weakRefRouter = weakref.ref(router)
		self._logger = logging.getLogger(__name__)
		self._condition = threading.Condition()
		self._messageHandler = BoxRouterMessageHandler(self._weakRefRouter, self)
		super(AstroprintBoxRouterClient, self).__init__(hostname)

	def __del__(self):
		self.unregisterEvents()

	def send(self, data):
		with self._condition:
			if not self.terminated:
				try:
					super(AstroprintBoxRouterClient, self).send(data)

				except socket.error as e:
					self._logger.error('Error raised during send: %s' % e)

					self._error = True

					#Something happened to the link. Let's try to reset it
					self.close()

	def ponged(self, pong):
		if str(pong) == LINE_CHECK_STRING:
			self.outstandingPings -= 1

	def lineCheck(self, timeout=30):
		while not self.terminated:
			sleep(timeout)
			if self.terminated:
				break

			if self.outstandingPings > 0:
				self._logger.error('The line seems to be down')

				router = self._weakRefRouter()
				router.close()
				router._doRetry()
				break

			if time() - self._lastReceived > timeout:
				try:
					self.send(PingControlMessage(data=LINE_CHECK_STRING))
					self.outstandingPings += 1

				except socket.error:
					self._logger.error("Line Check failed to send")

					#retry connection
					router = self._weakRefRouter()
					router.close()
					router._doRetry()

		self._lineCheckThread = None

	def terminate(self):
		#This is code to fix an apparent error in ws4py
		try:
			self._th = None #If this is not freed, the socket can't be freed because of circular references
			super(AstroprintBoxRouterClient, self).terminate()

		except AttributeError as e:
			if self.stream is None:
				self.environ = None
			else:
				raise e

	def opened(self):
		self.outstandingPings = 0
		self._lineCheckThread = threading.Thread(target=self.lineCheck)
		self._lineCheckThread.daemon = True
		self._error = False
		self._lineCheckThread.start()

	def closed(self, code, reason=None):
		#only retry if the connection was terminated by the remote or a link check failure (silentReconnect)
		router = self._weakRefRouter()

		if self._error or (self.server_terminated and router and router.connected):
			router.close()
			router._doRetry()

	def received_message(self, m):
		self._lastReceived = time()
		msg = json.loads(str(m))

		method  = getattr(self._messageHandler, msg['type'], None)
		if method:
			response = method(msg)
			if response is not None:
				self.send(json.dumps(response))

		else:
			self._logger.warn('Unknown message type [%s] received' % msg['type'])

	def registerEvents(self):
		if not self._systemListener:
			self._systemListener = SystemListener(self._weakRefRouter)
			printerManager().registerCallback(self._systemListener)

	def unregisterEvents(self):
		if self._systemListener:
			printerManager().unregisterCallback(self._systemListener)
			self._systemListener.cleanup()
			self._systemListener = None

class AstroprintBoxRouter(object):
	RETRY_SCHEDULE = [2, 2, 4, 10, 20, 30, 60, 120, 240, 480, 3600, 10800, 28800, 43200, 86400, 86400] #seconds to wait before retrying. When all exahusted it gives up

	STATUS_DISCONNECTED = 'disconnected'
	STATUS_CONNECTING = 'connecting'
	STATUS_CONNECTED = 'connected'
	STATUS_ERROR = 'error'

	def __init__(self):
		self._settings = settings()
		self._logger = logging.getLogger(__name__)
		self._eventManager = eventManager()
		self._pendingClientRequests = {}
		self._retries = 0
		self._retryTimer = None
		self._boxId = None
		self._ws = None
		self._silentReconnect = False
		self.status = self.STATUS_DISCONNECTED
		self.connected = False
		self.authenticated = False

		self._logger.info('This box has id %s' % self.boxId)

		self._eventManager.subscribe(Events.NETWORK_STATUS, self._onNetworkStateChanged)
		self._eventManager.subscribe(Events.NETWORK_IP_CHANGED, self._onIpChanged)

		self._address = self._settings.get(['cloudSlicer','boxrouter'])

		self._eventSender = EventSender(self)

		if self._address:
			self.boxrouter_connect()

		else:
			self._logger.error('cloudSlicer.boxrouter not present in config file')

	def shutdown(self):
		self._logger.info('Shutting down BoxRouter')

		if self._retryTimer:
			self._retryTimer.cancel()
			self._retryTimer = None

		self._eventManager.unsubscribe(Events.NETWORK_STATUS, self._onNetworkStateChanged)
		self._eventManager.unsubscribe(Events.NETWORK_IP_CHANGED, self._onIpChanged)
		self._pendingClientRequests = None
		self.boxrouter_disconnect()

		#make sure we destroy the singleton
		global _instance
		_instance = None

	@property
	def boxId(self):
		if not self._boxId:
			boxIdFile = "%s/box-id" % self._settings.getConfigFolder()

			if os.path.exists(boxIdFile):
				with open(boxIdFile, 'r') as f:
					self._boxId = f.read().strip()

			if not self._boxId:
				self._boxId = uuid.uuid4().hex

				with open(boxIdFile, 'w') as f:
					f.write(self._boxId)

		return self._boxId

	def boxrouter_connect(self):
		if not networkManager().isOnline():
			return False

		if not self.connected:
			from octoprint.server import userManager

			loggedUser = self._settings.get(['cloudSlicer', 'loggedUser'])
			if loggedUser and userManager:
				user = userManager.findUser(loggedUser)

				if user and user.is_authenticated:
					self._publicKey = user.publicKey
					self._privateKey = user.privateKey

					if self._publicKey and self._privateKey:
						self.status = self.STATUS_CONNECTING
						self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status)

						try:
							if self._retryTimer:
								#This is in case the user tried to connect and there was a pending retry
								self._retryTimer.cancel()
								self._retryTimer = None
								#If it fails, the retry sequence should restart
								self._retries = 0

							if self._ws and not self._ws.terminated:
								self._ws.terminate()

							self._ws = AstroprintBoxRouterClient(self._address, self)
							self._ws.connect()
							self.connected = True

						except Exception as e:
							self._logger.error("Error connecting to boxrouter: %s" % e)
							self.connected = False
							self.status = self.STATUS_ERROR
							self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status)

							if self._ws:
								self._ws.terminate()
								self._ws = None

							self._doRetry(False) #This one should not be silent

						return True

		return False

	def boxrouter_disconnect(self):
		self.close()

	def close(self):
		if self.connected:
			self.authenticated = False
			self.connected = False

			self._publicKey = None
			self._privateKey = None
			self.status = self.STATUS_DISCONNECTED
			self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);

			if self._ws:
				self._ws.unregisterEvents()
				if not self._ws.terminated:
					self._ws.terminate()

				self._ws = None

	def _onNetworkStateChanged(self, event, state):
		if state == 'offline':
			if self.connected:
				self._logger.info('Device is offline. Closing box router socket.')
				self.boxrouter_disconnect()

		elif state == 'online':
			if not self.connected:
				self._logger.info('Device is online. Attempting to connect to box router.')
				self.boxrouter_connect()

		else:
			self._logger.warn('Invalid network state (%s)' % state)

	def _onIpChanged(self, event, ipAddress):
		self._logger.info("BoxRouter detected IP Address changed to %s" % ipAddress)
		self.close()
		self._doRetry()

	# def _error(self, err):
	# 	self._logger.error('Unkonwn error in the connection with AstroPrint service: %s' % err)
	# 	self.status = self.STATUS_ERROR
	# 	self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status);
	# 	self.close()
	# 	self._doRetry()

	def _doRetry(self, silent=True):
		if self._retries < len(self.RETRY_SCHEDULE):
			def retry():
				self._retries += 1
				self._logger.info('Retrying boxrouter connection. Retry #%d' % self._retries)
				self._silentReconnect = silent
				self._retryTimer = None
				self.boxrouter_connect()

			if not self._retryTimer:
				self._logger.info('Waiting %d secs before retrying...' % self.RETRY_SCHEDULE[self._retries])
				self._retryTimer = threading.Timer(self.RETRY_SCHEDULE[self._retries] , retry )
				self._retryTimer.start()

		else:
			self._logger.info('No more retries. Giving up...')
			self.status = self.STATUS_DISCONNECTED
			self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status)
			self._retries = 0
			self._retryTimer = None

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

	def cancelRetry(self):
		if self._retryTimer:
			self._retryTimer.cancel()
			self._retryTimer = None

	def completeClientRequest(self, reqId, data):
		if reqId in self._pendingClientRequests:
			req = self._pendingClientRequests[reqId]
			del self._pendingClientRequests[reqId]

			if req["callback"]:
				args = req["args"] or []
				req["callback"](*([data] + args))

		else:
			self._logger.warn('Attempting to deliver a client response for a request[%s] that\'s no longer pending' % reqId);

	def broadcastEvent(self, event, data):
		self._eventSender.sendUpdate(event, data)

	def broadcastLastUpdate(self, event):
		self._eventSender.sendLastUpdate(event)

	def sendRequestToClient(self, clientId, type, data, timeout, respCallback, args=None):
		reqId = uuid.uuid4().hex

		if self.send({
			'type': 'request_to_client',
			'data': {
				'clientId': clientId,
				'timeout': timeout,
				'reqId': reqId,
				'type': type,
				'payload': data
			}
		}):
			self._pendingClientRequests[reqId] = {
				'callback': respCallback,
				'args': args,
				'timeout': timeout
			}

	def sendEventToClient(self, clientId, type, data):
		self.send({
			'type': 'send_event_to_client',
			'data': {
				'clientId': clientId,
				'eventType': type,
				'eventData': data
			}
		})

	def send(self, data):
		if self._ws and self.connected:
			self._ws.send(json.dumps(data))
			return True

		else:
			self._logger.error('Unable to send data: Socket not active')
			return False

	def processAuthenticate(self, data):
		if data:
			self._silentReconnect = False

			if 'error' in data:
				self._logger.warn(data['message'] if 'message' in data else 'Unkonwn authentication error')
				self.status = self.STATUS_ERROR
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status)
				self.close()

			elif 'success' in data:
				self._logger.info("Connected to astroprint service")
				self.authenticated = True
				self._retries = 0
				self._retryTimer = None
				self.status = self.STATUS_CONNECTED
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.status)

			return None

		else:
			from octoprint.server import VERSION

			nm = networkManager()
			sm = softwareManager()

			authData = {
				'silentReconnect': self._silentReconnect,
				'boxId': self.boxId,
				'variantId': sm.variant['id'],
				'boxName': nm.getHostname(),
				'swVersion': VERSION,
				'platform': sm.platform,
				'localIpAddress': nm.activeIpAddress,
				'publicKey': self._publicKey,
				'privateKey': self._privateKey
			}

			pkgId = sm.mfPackageId
			if pkgId:
				authData['mfPackageId'] = pkgId

			return {
				'type': 'auth',
				'data': authData
			}
