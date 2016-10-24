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
import uuid

import astroprint.util as processesUtil

from octoprint.settings import settings
from astroprint.webrtc.janus import Plugin, Session, KeepAlive
from astroprint.boxrouter import boxrouterManager
from astroprint.network.manager import networkManager
from astroprint.camera import cameraManager
from astroprint.util import interval

from blinker import signal


class WebRtc(object):
	def __init__(self):
		self._connectedPeers = {}
		self._logger = logging.getLogger(__name__)
		self._peerCondition = threading.Condition()
		self._JanusProcess = None
		self.videoId = 1
		initialized = signal('initialized')
		self.peersDeadDetacher = None

	def ensureJanusRunning(self):
		if len(self._connectedPeers.keys()) <= 0:
			return self.startJanus()
		else:
			return True #Janus was running before it

	#def ensureGstreamerRunning(self):
	#	cam = cameraManager()
	#	if cam.open_camera():
	#		if not cam.start_video_stream():
	#			self._logger.error('Managing Gstreamer error in WebRTC object')
				#Janus is forced to be closed
	#			self.stopJanus()
	#			return False
	#		return False
	#	else:
	#		return True

	def shutdown(self):
		self._logger.info('Shutting Down WebRtcManager')
		self.stopJanus()

	def startLocalSession(self, sessionId):
		with self._peerCondition:
			self._connectedPeers[sessionId] = "local";
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

				if len(webRtcManager()._connectedPeers.keys()) == 0:
					#last session
					self.stopGStreamer()
					self.stopJanus()

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
					self.stopGStreamer()
					self.stopJanus()

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
					self.sendEventToPeer(self._connectedPeers[sessionId], 'stopConnection')
					del self._connectedPeers[sessionId]

				self._logger.info("There are %d peers left.", len(self._connectedPeers))

				if len(self._connectedPeers.keys()) == 0:
					#last session
					self.stopGStreamer()
					self.stopJanus()
					ready = signal('manage_fatal_error_webrtc')
					ready.disconnect(self.closeAllSessions)

	def closeAllSessions(self,sender,message):

		self._logger.info("Closing all streaming sessions")

		for key in self._connectedPeers.keys():
			if self._connectedPeers[key] != 'local':
				if message:
					self.sendEventToPeer(self._connectedPeers[key], sender, message)
				self.closePeerSession(key)
			else:
				self.closeLocalSession(key)

		self.stopJanus()

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

			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'watch','id':self.videoId})

	def setSessionDescriptionAndStart(self, sessionId, data):

		try:
			peer = self._connectedPeers[sessionId]

		except KeyError:
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None
			self.sendEventToPeers('stopConnection')

		if peer:
			#Janus starting state
			self._connectedPeers[sessionId].streamingPlugin.set_session_description(data['type'],data['sdp'])
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'start'})
			#able to serve video
			self.startGStreamer()


	def tickleIceCandidate(self, sessionId, candidate, sdp_mid, sdp_mline_index):
		self._connectedPeers[sessionId].streamingPlugin.add_ice_candidate(candidate, sdp_mid, sdp_mline_index)

	def pongCallback(self, data, key):

		if 'pong' != data:
			if 'error' in data:
				self._logger.error('Webrtc client lost: %s. Automatic peer session closing...',data['error'])
			self.closePeerSession(key)

	def pingPongRounder(self,params=None):

		for key in self._connectedPeers.keys():
			if self._connectedPeers[key] != 'local':
				#sendRequestToClient(self, clientId, type, data, timeout, respCallback)
				boxrouterManager().sendRequestToClient(self._connectedPeers[key].clientId, 'ping',None,10, self.pongCallback, [key])

	def startGStreamer(self):
		#Start Gstreamer
		if not cameraManager().start_video_stream():
			self._logger.error('Managing Gstreamer error in WebRTC object')
			self.stopJanus()

	def startJanus(self):
		#Start janus command here

		nm = networkManager()

		args = ['/opt/janus/bin/./janus']

		if not nm.isOnline():

			args = ['/opt/janus/bin/./janus','--config=/opt/janus/etc/janus/janus.cfg.local']

		try:
			self._JanusProcess = subprocess.Popen(
		    	args,
		    	stdout=subprocess.PIPE
			)

		except Exception, error:
			self._logger.error("Error initiating janus process: %s" % str(error))
			self._JanusProcess = None
			self.sendEventToPeers('stopConnection')
			return False

		if self._JanusProcess:
			from requests import Session

			session = Session()
			response = None

			tryingCounter = 0
			while response is None:
				time.sleep(0.3)

				try:
					response = session.post(
					    url='http://127.0.0.1:8088',
					    data={
						 "message":{
						 	"request": 'info',
         					 	"transaction": 'ready'
						  	}
					    }
					)

				except Exception, error:
					#self._logger.warn('Waiting for Janus initialization')
					tryingCounter += 1

					if tryingCounter >= 100:
						self._logger.error(error)
						return False

			ready = signal('manage_fatal_error')
			ready.connect(self.closeAllSessions)

			#START TIMER FOR LOST PEERS
			self.peersDeadDetacher = interval(30.0,self.pingPongRounder,None)
			self.peersDeadDetacher.start()

			return True

	def stopJanus(self):

		try:
			if self._JanusProcess is not None:
				self._JanusProcess.kill()
				self.sendEventToPeers('stopConnection')
				self._connectedPeers = {}

				#STOP TIMER FOR LOST PEERS
				self.peersDeadDetacher.cancel()

				return True
		except Exception, error:
			self._logger.error("Error stopping Janus: it is already stopped. Error: %s" % str(error))
			return False


	def stopGStreamer(self):
		cameraManager().stop_video_stream()

	def sendEventToPeers(self, type, data=None):
		for key in self._connectedPeers.keys():
			if self._connectedPeers[key] != 'local':
				self.sendEventToPeer(self._connectedPeers[key], type, data)

	def sendEventToPeer(self, peer, type, data=None):
		boxrouterManager().sendEventToClient(peer.clientId, type, data)

class StreamingPlugin(Plugin):
	name = 'janus.plugin.streaming'

class ConnectionPeer(object):

	def __init__(self, clientId, parent):
		self.session = None
		self.clientId = clientId
		self.sessionKa = None
		self.id = None
		self.streamingPlugin = None
		self._parent = parent

	#CONNECTION
	#def connection_on_opened(self,connection):
	#	logging.info('CONNECTION ON OPENED')

	#def connection_on_closed(self,connection,**kw):
	#	logging.info('CONNECTION ON CLOSED')

	def connection_on_message(self,connection,message):

		messageToReturn = json.loads(str(message))

		if self.session is not None and 'session_id' in messageToReturn and messageToReturn['session_id'] != self.session.id:
			return

		if 'janus' in messageToReturn and messageToReturn['janus'] == 'hangup':
			#Finish camera session caused by user or exception
			self._parent.closePeerSession(messageToReturn['session_id'])
		elif 'jsep' in messageToReturn:
			self.sendEventToPeer('getSdp',messageToReturn)

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

		self.session.register_plugin(self.streamingPlugin);
		self.session.connect();


		self.sessionKa = KeepAlive(self.session)
		self.sessionKa.daemon = True
		self.sessionKa.start()

		waitingState = sem.wait(5)
		sem.clear()

		if waitingState:

			return self.session.id

		else:

			logging.error("Error initializing Janus: session can not be started")
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
		boxrouterManager().sendEventToClient(self.clientId, type, data)

