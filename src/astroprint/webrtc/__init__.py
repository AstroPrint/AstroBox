# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

# singleton
_instance = None

def WebRtcManager():
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

from octoprint.settings import settings
from astroprint.webrtc.janus import Plugin, Session, KeepAlive
from astroprint.boxrouter import boxrouterManager

class WebRtc(object):
	def __init__(self):
		self._connectedPeers = {}
		self._logger = logging.getLogger(__name__)
		self._peerCondition = threading.Condition()
		self._JanusProcess = None
		self._GStreamerProcess = None
		self._GStreamerProcessArgs = None
		self.videoId = 1

	def startPeerSession(self, clientId):
		with self._peerCondition:
			if len(self._connectedPeers.keys()) == 0:
				#self.startGStreamer()
				self.startJanus()

			peer = ConnectionPeer(clientId, self)

			logging.info('SESSIONID ANTES')
			
			sessionId = peer.start()
			
			logging.info(sessionId)
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
				logging.info(sessionId)
				try:
					logging.info('A')
					logging.info(self._connectedPeers)
					peer = self._connectedPeers[sessionId]
					logging.info('B')
				except KeyError:
					logging.info('C')
					self._logger.warning('Session [%s] for peer not found' % sessionId)
					peer = None
					logging.info('D')
				logging.info('E')
				if peer:
					logging.info('F')
					peer.streamingPlugin.send_message({'request':'destroy'})
					peer.close()
					self.sendEventToPeer('stopConnection',self._connectedPeers[sessionId])
					del self._connectedPeers[sessionId]
				logging.info('G')
				if len(self._connectedPeers.keys()) == 0:
					logging.info('H')
					self.stopGStreamer()
					self.stopJanus()
				logging.info('I')
				
	def preparePlugin(self, sessionId):
		
		logging.info('PREPARE_PLUGIN')
		try:
			logging.info('PREPARE_PLUGIN TRY')
			peer = self._connectedPeers[sessionId]

		except KeyError:
			logging.info('PREPARE_PLUGIN ERROR')
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None
			self.sendEventToPeers('stopConnection',None)

		if peer:
			logging.info('PREPARE_PLUGIN LISTOING')
			peer.streamingPlugin.send_message({'request':'list'})
			logging.info('PREPARE_PLUGIN LISTED')
			
			videoEncodingSelected = settings().get(["camera", "encoding"])
			videoSizeSelected = settings().get(["camera", "size"])
			videoFramerateSelected = settings().get(["camera", "framerate"])
			
			size = videoSizeSelected.split('x')
			
			if videoEncodingSelected == 'h264':
				self._GStreamerProcessArgs = 'gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! gdkpixbufoverlay location=/AstroBox/src/astroprint/static/img/astroprint_logo.png offset-x=480 offset-y=450 overlay-width=150 overlay-height=29 ! videoconvert ! "video/x-raw,framerate=' + videoFramerateSelected + '/1,width=' + size[0] + ',height=' + size[1] + '" ! omxh264enc ! video/x-h264,profile=high ! rtph264pay pt=96 ! queue ! udpsink host=127.0.0.1 port=8004'
				self.videoId = 1
			else:#VP8
				self._GStreamerProcessArgs = 'gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! gdkpixbufoverlay location=/AstroBox/src/astroprint/static/img/astroprint_logo.png offset-x=480 offset-y=450 overlay-width=150 overlay-height=29 ! videoconvert ! video/x-raw, framerate=' + videoFramerateSelected + '/1, width=' + size[0] + ', height=' + size[1] + ' ! vp8enc target-bitrate=500000 keyframe-max-dist=500 deadline=1 ! rtpvp8pay pt=96 ! udpsink host=127.0.0.1 port=8005'
				self.videoId = 2
			
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'watch','id':self.videoId})
			logging.info('PREPARE_PLUGIN WATCHED 2')

	def setSessionDescriptionAndStart(self, sessionId, data):

		try:
			logging.info('TRY')
			peer = self._connectedPeers[sessionId]

		except KeyError:
			logging.info('ERROR')
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None
			self.sendEventToPeers('stopConnection')

		if peer:
			#starting state
			logging.info('SETTING_DESCRIPTION')
			self._connectedPeers[sessionId].streamingPlugin.set_session_description(data['type'],data['sdp'])
			logging.info('SET_DESCRIPTION')
			logging.info('REQUEST_START ...')
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'start'})
			self.startGStreamer()
			logging.info('REQUEST_START')


	def tickleIceCandidate(self, sessionId, candidate, sdp_mid, sdp_mline_index):
		logging.info('TRICKLEICECANDIDATE')
		self._connectedPeers[sessionId].streamingPlugin.add_ice_candidate(candidate, sdp_mid, sdp_mline_index)

	def findProcess(self, processId ):
		ps= subprocess.Popen("ps -ef | grep "+processId, shell=True, stdout=subprocess.PIPE)
		output = ps.stdout.read()
		ps.stdout.close()
		ps.wait()
		logging.info('OUTPUT')
		logging.info(output)
		return output

	def isProcessRunning(self, processId):
		
		nameProcess = processId
		
		lastChar = processId[len(processId)-1]
		processId = processId[:-1]
		processId = processId + '[' + lastChar + ']'
		
		output = self.findProcess( processId )
		logging.info('output')
		logging.info(output)
		
		logging.info('nameProcess')
		logging.info(nameProcess)
		
		if nameProcess in output:
			logging.info('SEARCH TRUE')
			return True
		else:
			logging.info('SEARCH FALSE')
			return False

	def startGStreamer(self):
		
		logging.info('STARTGSTREAMER')
		
		try:
			if not self.isProcessRunning('gst'):
				self._GStreamerProcess = subprocess.Popen(
					self._GStreamerProcessArgs,
		    	 	shell=True
				)

		except Exception, error:
			self._logger.error("Error initiating GStreamer process: %s" % str(error))
			self._GStreamerProcess = None
			self.sendEventToPeers('stopConnection')

	def startJanus(self):
		#Start janus command here
		logging.info('START JANUS')
		args = ['/opt/janus/bin/./janus']

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
			while True:
				if 'HTTP/Janus sessions watchdog started' in self._JanusProcess.stdout.readline():
					import time
					time.sleep(3)
					break

	def stopJanus(self):
		try:
			if self._JanusProcess is not None:
				self._JanusProcess.kill()
		except Exception, error:
			self._logger.error("Error stopping Janus: it is already stopped. Error: %s" % str(error))
			

	def stopGStreamer(self):
		if self.isProcessRunning('gst'):
			for line in os.popen('ps ax | grep gst | grep -v grep'):
				fields = line.split()
				pid = fields[0]
				#os.kill(int(pid), signal.SIGKILL)
				subprocess.Popen(
					'kill -9 ' + pid, shell=True
				)
	
	def sendEventToPeers(self, type, data=None):
		
		for key in self._connectedPeers.keys():
			#'key=%s, value=%s' % (key, self._connectedPeers[key])
			boxrouterManager().send({
				'type': 'send_event_to_client',
				'data': {
					'clientId': self._connectedPeers[key].clientId,
					'eventType': type,
					'eventData': data
				}
			})
			
	def sendEventToPeer(self, type, data=None):
		
		boxrouterManager().send({
			'type': 'send_event_to_client',
			'data': {
				'clientId': data.clientId,
				'eventType': type,
				'eventData': None
			}
		})

class StreamingPlugin(Plugin):
	name = 'janus.plugin.streaming'

class ConnectionPeer(object):

	def __init__(self, clientId, parent):
		logging.info('INIT CONNECTIONPEER')
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
		logging.info('CONNECTION ON MESSAGE')

		messageToReturn = json.loads(str(message))

		if self.session is not None and 'session_id' in messageToReturn and messageToReturn['session_id'] != self.session.id:
			return

		if 'janus' in messageToReturn and messageToReturn['janus'] == 'hangup':
			self._parent.closePeerSession(messageToReturn['session_id'])
		elif 'jsep' in messageToReturn:
		#else:
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

		sem = threading.Semaphore(0)

		self.streamingPlugin = StreamingPlugin()
		self.session = Session('ws://127.0.0.1:8188', secret='d5faa25fe8e3438d826efb1cd3369a50')

		@self.session.on_plugin_attached.connect
		def receive_data(sender, **kw):
			sem.release()


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

		sem.acquire()
		
		logging.info('SELF.SESSION.ID')
		logging.info(self.session.id)

		return self.session.id

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

	def sendEventToPeer(self, type, data):
		boxrouterManager().send({
			'type': 'send_event_to_client',
			'data': {
				'clientId': self.clientId,
				'eventType': type,
				'eventData': data
			}
		})
