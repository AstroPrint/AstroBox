import threading
import logging
import re

import paho.mqtt.client as mqtt

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from .topics import MQTTTopics
from systemlistener import SystemListener


# singleton
_instance = None
creationLock = threading.Lock()

def mqttManager(deviceId=None):
	global _instance

	if _instance is None:
		if deviceId is not None:
			with creationLock:
				#check again because maybe another lock created it
				if _instance is None:
					_instance = MQTTClient(deviceId)
		else:
			logging.error('deviceId not specified when creating MQTT Manager')
			exit(1)

	return _instance

class MQTTClient(object):
	STATUS_DISCONNECTED = 'disconnected'
	STATUS_CONNECTING = 'connecting'
	STATUS_CONNECTED = 'connected'
	STATUS_ERROR = 'error'

	_topicRegex = re.compile(r'^3d-printer/[a-fA-F0-9]+/requests/([\w\-]+){1}((?:/[\w\-]*)*)$')

	def __init__(self, deviceId):
		self._settings = settings()
		self._deviceId = deviceId
		self._logger = logging.getLogger(__name__)
		self._eventManager = eventManager()
		self._eventManager.subscribe(Events.NETWORK_STATUS, self._onNetworkStateChanged)
		self._client = mqtt.Client(client_id=deviceId)
		self._topics = MQTTTopics()
		#self._client.enable_logger()
		#self._client.tls_set_context()
		self._client.on_connect = self._on_connect
		self._client.on_message = self._on_message
		self._client.on_diconnect = self._on_disconnect

	def connect(self, hostname, port=1083):
		from octoprint.server import userManager

		loggedUser = self._settings.get(['cloudSlicer', 'loggedUser'])
		if loggedUser and userManager:
			user = userManager.findUser(loggedUser)

			if user and user.is_authenticated:
				self._logger.info("Connecting to MQTT Broker [%s] on port [%d]" % (hostname, port))
				self._client.username_pw_set(user.publicKey, user.privateKey)
				self._eventManager.fire(Events.ASTROPRINT_STATUS, self.STATUS_CONNECTING)
				self._client.connect(hostname, port, 60)
				self._client.loop_start()
				self._systemListener = SystemListener(self)
				return

		self._logger.info('No user logged in. MQTT Connection impossible')

	def close(self):
		self._logger.info("Closing MQTT Broker connection")

		def closed():
			self._client.loop_stop()

		self._client.disconnect(closed)

	def shutdown(self):
		self.close()

	def publish(self, topic, data):
		self._client.publish('3d-printer/%s/events/%s' % (self._deviceId, topic), data)

	# The callback for when the client receives a CONNACK response from the server.
	def _on_connect(self, client, userdata, flags, rc):
		self._logger.info("Connected to MQTT Broker with result code [%d]" % rc)
		self._eventManager.fire(Events.ASTROPRINT_STATUS, self.STATUS_CONNECTED)

		# Subscribing in on_connect() means that if we lose the connection and
		# reconnect then subscriptions will be renewed.
		client.subscribe("3d-printer/%s/requests/#" % self._deviceId)

	def _on_disconnect(self, client, userdata, rc):
		self._systemListener.cleanup()
		self._systemListener = None

		if rc == 0:
			self._logger.info('MQTT Connection closed')
		else:
			self._logger.warn('MQTT Connection disconnected with [%d]', rc)

		self._eventManager.fire(Events.ASTROPRINT_STATUS, self.STATUS_DISCONNECTED)

	# The callback for when a PUBLISH message is received from the server.
	def _on_message(self, client, userdata, msg):
		#self._logger.info("MQTT message received on topic [%s]: %s" % (msg.topic, str(msg.payload)))

		topicMatches = self._topicRegex.match(msg.topic)

		if topicMatches:
			topic = topicMatches.group(1)
			try:
				func = getattr(self._topics, topic)
				func(topicMatches.group(2), msg.payload)

			except AttributeError:
				self._logger.warn('Topic not found [%s]', topic)

			except Exception as e:
				self._logger.error('Error processing MQTT Message', exc_info=True)

		else:
			self._logger.warn('Topic not valid: %s', msg.topic)

	def _onNetworkStateChanged(self, event, state):
		if state == 'offline':
			self._logger.info('Device is offline. Closing MQTT Network Loop.')
			self.close()

		elif state == 'online':
			self._logger.info('Device is online. Attempting to connect to MQTT Broker.')
			self.connect('boxrouter.astroprint.test', 1883)

		else:
			self._logger.warn('Invalid network state (%s)' % state)
