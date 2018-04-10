# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

# singleton
_instance = None

def webRtcManager():
	global _instance
	if _instance is None:
		_instance = WebRtc()
	return _instance

import logging
import threading
import subprocess
import json
import os
import signal
import re
import time
import requests

from blinker import signal

from octoprint.settings import settings
from astroprint.webrtc.janus import Plugin, Session, KeepAlive
from astroprint.boxrouter import boxrouterManager
from astroprint.network.manager import networkManager
from astroprint.camera import cameraManager
from astroprint.util import interval


class WebRtc(object):
	def __init__(self):
		self._connectedPeers = {}
		self._logger = logging.getLogger(__name__)
		self._peerCondition = threading.Condition()
		self._janusStartStopCondition = threading.Condition()
		self._JanusProcess = None
		self.videoId = 1
		self.peersDeadDetacher = None

	def shutdown(self):
		self._logger.info('Shutting Down WebRtcManager')
		self.stopJanus()

	def startLocalSession(self, sessionId):
		with self._peerCondition:
			self._connectedPeers[sessionId] = "local"
			return True

	def closeLocalSession(self, sessionId):
		with self._peerCondition:
			if len(self._connectedPeers.keys()) > 0:
				try:
					peer = self._connectedPeers[sessionId]
				except KeyError:
					self._logger.warning('Session [%s] for peer not found' % sessionId)
					peer = None

				if peer:
					del self._connectedPeers[sessionId]

				self._logger.info("There are %d peers left.", len(self._connectedPeers))

				if len(self._connectedPeers) == 0:
					#last session
					self.stopJanus()
					cameraManager().stop_video_stream()

			return True

	def startPeerSession(self, clientId):
		with self._peerCondition:
			if len(self._connectedPeers.keys()) == 0:
				#first session
				self.startJanus()

			peer = ConnectionPeer(clientId, self)

			sessionId = peer.start()

			if sessionId:
				self._connectedPeers[sessionId] = peer
				return sessionId

			else:
				#something went wrong, no session started. Do we still need Janus up?
				if len(self._connectedPeers.keys()) == 0:
					self.stopJanus()
					cameraManager().stop_video_stream()

				return None

	def closePeerSession(self, sessionId):
		with self._peerCondition:
			if len(self._connectedPeers.keys()) > 0:

				try:
					peer = self._connectedPeers[sessionId]
				except KeyError:
					self._logger.warning('Session [%s] for peer not found' % sessionId)
					peer = None

				if peer:
					peer.streamingPlugin.send_message({'request':'destroy', 'id': sessionId})
					peer.close()
					peer.sendEventToPeer('stopConnection')
					del self._connectedPeers[sessionId]

				self._logger.info("There are %d peers left.", len(self._connectedPeers))

				if len(self._connectedPeers.keys()) == 0:
					#last session
					self.stopJanus()
					cameraManager().stop_video_stream()

	def closeAllSessions(self, sender= None, message= None):
		self._logger.info("Closing all streaming sessions")

		for sessionId in self._connectedPeers.keys():
			peer = self._connectedPeers[sessionId]
			#if peer != 'local':
			if isinstance(peer, ConnectionPeer):
				if message:
					peer.sendEventToPeer("cameraError", message)

				self.closePeerSession(sessionId)
			else:
				self.closeLocalSession(sessionId)

		return self.stopJanus()

	def preparePlugin(self, sessionId):
		try:
			peer = self._connectedPeers[sessionId]

		except KeyError:
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None
			self.sendEventToPeers('stopConnection')

		if peer:
			peer.streamingPlugin.send_message({'request':'list'})

			videoEncodingSelected = settings().get(["camera", "encoding"])

			if videoEncodingSelected == 'h264':
				self.videoId = 1

			else:#VP8
				self.videoId = 2

			peer.streamingPlugin.send_message({'request':'watch','id':self.videoId})

	def setSessionDescriptionAndStart(self, sessionId, data):
		try:
			peer = self._connectedPeers[sessionId]

		except KeyError:
			self._logger.warning('SetSessionDescription: Peer with session [%s] is not found' % sessionId)
			peer = None
			self.sendEventToPeers('stopConnection')

		if peer:
			#Janus starting state
			self._connectedPeers[sessionId].streamingPlugin.set_session_description(data['type'],data['sdp'])
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'start'})
			#able to serve video
			self.startVideoStream()


	def tickleIceCandidate(self, sessionId, candidate, sdp_mid, sdp_mline_index):
		if sessionId in self._connectedPeers:
			self._connectedPeers[sessionId].streamingPlugin.add_ice_candidate(candidate, sdp_mid, sdp_mline_index)
		else:
			self._logger.warning('TickleIceCandidate: Peer with session [%s] is not found' % sessionId)

	def reportEndOfIceCandidates(self, sessionId):
		if sessionId in self._connectedPeers:
			self._connectedPeers[sessionId].streamingPlugin.send_message({
				'janus': 'trickle',
				'candidate': {
					'completed': True
				}
			})
		else:
			self._logger.warning('reportEndOfIceCandidates: Peer with session [%s] is not found' % sessionId)

	def pongCallback(self, data, key):
		if 'pong' != data:
			if 'error' in data:
				self._logger.error('Webrtc client lost: %s. Automatic peer session closing...',data['error'])

			self.closePeerSession(key)

	def pingPongRounder(self,params=None):
		for sessionId in self._connectedPeers.keys():
			peer = self._connectedPeers[sessionId]
			#if peer != 'local':
			if isinstance(peer, ConnectionPeer):
				try:
					boxrouterManager().sendRequestToClient(peer.clientId, 'ping', None, 10, self.pongCallback, [sessionId])

				except:
					self._logger.error('Error sending ping to peer %s' % peer.clientId, exc_info = True)

	def startVideoStream(self):
		#Start Video Stream
		def startDone(success):
			if not success:
				self._logger.error('Managing GStreamer error in WebRTC object')
				self.stopJanus()

		cameraManager().start_video_stream(startDone)

	def startJanus(self):
		with self._janusStartStopCondition:
			#Start janus command here
			if self._JanusProcess and self._JanusProcess.returncode is None:
				self._logger.debug('Janus was already running')
				return True #already running

			args = ['/usr/bin/janus', '-F', '/etc/astrobox/janus', '-C']

			nm = networkManager()
			if nm.isOnline():
				args.append('/etc/astrobox/janus/janus.cfg')
			else:
				args.append('/etc/astrobox/janus/janus.cfg.local')

			try:
				self._JanusProcess = subprocess.Popen(
					args,
					stdout=subprocess.PIPE
				)

			except Exception, error:
				self._logger.error("Error initiating janus process: %s" % str(error))
				self._JanusProcess = None
				self.sendEventToPeers('stopConnection')

			if self._JanusProcess:
				self._logger.debug('Janus Starting...')

				response = None
				tryingCounter = 0
				while response is None:
					time.sleep(0.3)

					try:
						response = requests.post(
							url= 'http://127.0.0.1:8088',
							data= {
							 	"message":{
									"request": 'info',
									"transaction": 'ready'
								}
							}
						)

					except Exception, error:
						self._logger.debug('Waiting for Janus initialization. Responded with: %s' % error)
						tryingCounter += 1

						if tryingCounter >= 100:
							self._logger.error("Janus failed to start: %s" % error)
							return False

				self._logger.debug('Janus Started.')

				#Connect the signal for fatal errors when they happen
				ready = signal('manage_fatal_error_webrtc')
				ready.connect(self.closeAllSessions)

				#START TIMER FOR LOST PEERS
				self.peersDeadDetacher = interval(30.0, self.pingPongRounder, None)
				self.peersDeadDetacher.start()

				return True

			return False

	def stopJanus(self):
		with self._janusStartStopCondition:
			try:
				if self._JanusProcess is not None:
					#it's possible that a new client came it while stopping the camera feed
					#in that case we should not try to stop it
					if self._JanusProcess.returncode is None:
						self._logger.debug('Attempting to terminate the Janus process')
						self._JanusProcess.terminate()

						attempts = 6
						while self._JanusProcess.returncode is None and attempts > 0:
							time.sleep(0.3)
							self._JanusProcess.poll()
							attempts -= 1

						if self._JanusProcess.returncode is None:
							#still not terminated
							self._logger.debug('Janus didn\'t terminate nicely, let\'s kill it')
							self._JanusProcess.kill()
							self._JanusProcess.wait()

						self._logger.debug('Janus Stopped')

					self._JanusProcess = None
					self.sendEventToPeers('stopConnection')
					self._connectedPeers = {}

					#STOP TIMER FOR LOST PEERS
					if self.peersDeadDetacher:
						self.peersDeadDetacher.cancel()

					ready = signal('manage_fatal_error_webrtc')
					ready.disconnect(self.closeAllSessions)

					return True

			except Exception as e:
				self._logger.error("Error stopping Janus. Error: %s" % e)

			return False

	def restartJanus(self):
		return self.stopJanus() and self.startJanus()

	def sendEventToPeers(self, type, data=None):
		for peer in self._connectedPeers:
			#if peer != 'local':
			if isinstance(peer, ConnectionPeer):
				peer.sendEventToPeer(type, data)

class StreamingPlugin(Plugin):
	name = 'janus.plugin.streaming'

class ConnectionPeer(object):
	def __init__(self, clientId, parent):
		self._logger = logging.getLogger(__name__ + ':ConnectionPeer')
		self.session = None
		self.clientId = clientId
		self.sessionKa = None
		self.id = None
		self.streamingPlugin = None
		self._parent = parent

	#CONNECTION
	#def connection_on_opened(self,connection):
	#	logging.info('CONNECTION ON OPENED')

	#def connection_on_closed(self, connection, **kw):
	#	self._logger.warn('Lost connection with Janus')

	def connection_on_message(self, connection, message):
		messageToSend = json.loads(str(message))

		if self.session is not None and 'session_id' in messageToSend and messageToSend['session_id'] != self.session.id:
			return

		if 'janus' in messageToSend and messageToSend['janus'] == 'hangup':
			#Finish camera session caused by user or exception
			self._parent.closePeerSession(messageToSend['session_id'])

		elif 'jsep' in messageToSend:
			self.sendEventToPeer('getSdp', messageToSend)

	#SESSION
	#def session_on_connected(self,session,**kw):
	#	logging.info('SESSION ON OPENED')

	#def session_on_disconnected(self,session,**kw):
	#	logging.info('SESSION ON CLOSED')

	#def session_on_message(self,session,**kw):
	#	logging.info('SESSION ON MESSAGE')

	#def session_on_plugin_attached(self,session,**kw):
	#	logging.info('SESSION ON PLUGIN ATTACHED')

	#def session_on_plugin_detached(self,session,**kw):
	#	logging.info('SESSION ON PLUGIN DETACHED')


	#PLUGIN
	#def streamingPlugin_on_message(self,plugin,**kw):
	#	logging.info('STREAMINGPLUGIN ON MESSAGE')

	#def streamingPlugin_on_attached(self,plugin,**kw):
	#	logging.info('STREAMINGPLUGIN ON ATTACHED')

	#def streamingPlugin_on_detached(self,plugin,**kw):
	#	logging.info('STREAMINGPLUGIN ON DETACHED')

	#def streamingPlugin_on_webrtcup(self,plugin,**kw):
	#	logging.info('STREAMINGPLUGIN ON WEBRTCUP')

	#def streamingPlugin_on_hangup(self,plugin,**kw):
	#	logging.info('STREAMINGPLUGIN ON HANGUP')

	def start(self):
		sem = threading.Event()

		self.streamingPlugin = StreamingPlugin()
		self.session = Session('ws://127.0.0.1:8188', secret='d5faa25fe8e3438d826efb1cd3369a50')

		@self.session.on_plugin_attached.connect
		def receive_data(sender, **kw):
			#wait until Janus plugin is not attached
			sem.set()


		#CONNECTION
		#self.session.cxn_cls
		#
		#SIGNALS
		#
		# Signal fired when `Connection` has been established.
			#	on_opened = blinker.Signal()
		#self.session.cxn_cls.on_opened.connect(self.connection_on_opened)

		#
		# Signal fired when `Connection` has been closed.
		#	on_closed = blinker.Signal()
		#self.session.cxn_cls.on_closed.connect(self.connection_on_closed)

		#
		# Signal fired when `Connection` receives a message
		#	on_message = blinker.Signal()
		self.session.cxn_cls.on_message.connect(self.connection_on_message)

		##


		#SESSION
		#self.session
		#
		#SIGNALS
		#
		# Signal fired when `Session` has been connected.
		#	on_connected = blinker.Signal()
		#self.session.on_connected.connect(self.session_on_connected)

		#
		# Signal fired when `Session` has been disconnected.
		#	on_disconnected = blinker.Signal()
		#self.session.on_disconnected.connect(self.session_on_disconnected)

		#
		# Signal fired when a `Session` level message is received.
		#	on_message = blinker.Signal()
		#self.session.on_message.connect(self.session_on_message)

		#
		# Signal fired when a `Session` `Plugin` been attached.
		#	on_plugin_attached = blinker.Signal()
		#self.session.on_plugin_attached.connect(self.session_on_plugin_attached)

		#
		# Signal fired when a `Session` `Plugin` been detached.
		#	on_plugin_detached = blinker.Signal()
		#self.session.on_plugin_detached.connect(self.session_on_plugin_detached)

		##


		#PLUGIN
		#self.streamingPlugin
		#
		#SIGNALS
		#
		# Signal fired when a `Plugin` is attached to a `Session`.
		#	on_attached = blinker.Signal()
		#self.streamingPlugin.on_attached.connect(self.streamingPlugin_on_attached)

		#
		# Signal fired when a `Plugin` is attached to a `Session`.
		#	on_detached = blinker.Signal()
		#self.streamingPlugin.on_detached.connect(self.streamingPlugin_on_detached)

		#
		# Signal fired when a `Plugin` receives a message.
		#	on_message = blinker.Signal()
		#self.streamingPlugin.on_message.connect(self.streamingPlugin_on_message)
		#

		# Signal fired when webrtc for a `Plugin` has been setup.
		#	on_webrtcup = blinker.Signal()
		#self.streamingPlugin.on_webrtcup.connect(self.streamingPlugin_on_webrtcup)


		#
		# Signal fired when webrtc session for a `Plugin` has been torn down.
		#	on_hangup = blinker.Signal()
		#self.streamingPlugin.on_hangup.connect(self.streamingPlugin_on_hangup)

		##

		self.session.register_plugin(self.streamingPlugin)
		try:
			self.session.connect()
		except Exception as e:
			if e.errno == 111:
				#Connection refused
				self._logger.warn('Janus was unavailable. Restarting...')
				if self._parent.restartJanus():
					self._logger.info('Janus succesfully restarted')
					self.session.connect()
				else:
					self._logger.error('Janus could not be restarted')
					return None

		self.sessionKa = KeepAlive(self.session)
		self.sessionKa.daemon = True
		self.sessionKa.start()

		waitingState = sem.wait(5)
		sem.clear()

		if waitingState:
			return self.session.id

		else:
			self._logger.error("Error initializing Janus: session can not be started")
			return None

	def close(self):
		#stop the keepalive worker
		self.sessionKa.stop()
		self.sessionKa.join()
		self.sessionKa = None

		#kill the current session
		self.session.unregister_plugin(self.streamingPlugin)
		self.session.disconnect()
		self.session = None
		self.streamingPlugin = None

	def sendEventToPeer(self, type, data= None):
		try:
			boxrouterManager().sendEventToClient(self.clientId, type, data)

		except:
			self._logger.error('Error sending event [%s] to peer %s' % (type, self.clientId), exc_info = True)

