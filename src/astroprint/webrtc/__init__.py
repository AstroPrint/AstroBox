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

from astroprint.webrtc.janus import Plugin, Session, KeepAlive
from astroprint.boxrouter import boxrouterManager

class WebRtc(object):
	def __init__(self):
		self._connectedPeers = {}
		self._logger = logging.getLogger(__name__)
		self._peerCondition = threading.Condition()
		self._process = None

	def startPeerSession(self, clientId):
		with self._peerCondition:
			logging.info('STARTPEERSESSION')
			if len(self._connectedPeers.keys()) == 0:
				self.startJanus()

			peer = ConnectionPeer(clientId)

			sessionId = peer.start()
			if sessionId:
				self._connectedPeers[sessionId] = peer
				return sessionId

			else:
				#something went wrong, no session started. Do we still need Janus up?
				if len(self._connectedPeers.keys()) == 0:
					self.stopJanus()

				return None

	def closePeerSession(self, sessionId):
		with self._peerCondition:
			try:
				peer = self._connectedPeers[sessionId]

			except KeyError:
				self._logger.warning('Session [%s] for peer not found' % sessionId)
				peer = None

			if peer:
				peer.close()
				del self._connectedPeers[sessionId]

			if len(self._connectedPeers.keys()) == 0:
				self.stopJanus()
				
	def preparePlugin(self, sessionId):
		
		try:
			logging.info('PREPAREPLUGIN')
			peer = self._connectedPeers[sessionId]

		except KeyError:
			logging.info('PREPAREPLUGIN ERROR')
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None

		if peer:
			logging.info('PREPAREPLUGIN LIST AND 2')
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'list'})	
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'switch','id':2})
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'watch','id':2})
			#self._connectedPeers[sessionId].streamingPlugin.set_session_description(data['type'],data['sdp'])
			#preparing state
			#self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'start'})
			#self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'setup_media'})
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'enable','id':2})

	def setSessionDescriptionAndStart(self, sessionId, data):
		
		try:
			peer = self._connectedPeers[sessionId]
			
		except KeyError:
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None

		if peer:
			logging.info('SESSIONDESCRIPTION')
			logging.info(data['type'])
			logging.info(data['sdp'])
			
			#preparing state
			
			#starting state
			self._connectedPeers[sessionId].streamingPlugin.set_session_description(data['type'],data['sdp'])
			#self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'jsep'})
			#self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'setup_media'})
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'switch','id':2})
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'jsep'})
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'start'})


	def tickleIceCandidate(self, sessionId, candidate, sdp_mid, sdp_mline_index):
		logging.info('ENTRA EN tickleIceCandidate')
		
		"""try:
			logging.info('TRY')
			logging.info(self._connectedPeers[sessionId])
			peer = self._connectedPeers[sessionId]

		except KeyError:
			logging.info('EXCP')
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None
		
		if peer:
			"""
		logging.info('ADD_ICE_CANDIDATE')
		self._connectedPeers[sessionId].streamingPlugin.add_ice_candidate(candidate, sdp_mid, sdp_mline_index)

	def startJanus(self):
		#Start janus command here
		
		args = ['/opt/janus/bin/./janus']

		try:
			self._process = subprocess.Popen(
		    	args,
		    	stdout=subprocess.PIPE
			)
		
		except Exception, error:
			self._logger.error("Error initiating janus process: %s" % str(error))
			self._process = None

		if self._process:
			while True:
				if 'HTTP/Janus sessions watchdog started' in self._process.stdout.readline():
					import time
					time.sleep(3)
					break
				
				

	def stopJanus(self):
		self._process.kill()

class StreamingPlugin(Plugin):
	name = 'janus.plugin.streaming'
	id = '2'

class ConnectionPeer(object):
	def __init__(self, clientId):
		self.session = None
		self.clientId = clientId
		self.sessionKa = None
		self.id = None
		self.streamingPlugin = None

	def recv_message(self):
		logging.info('MENSAJE RECIBIDO')
	
	
	#CONNECTION
	def connection_on_opened(self,connection):
		logging.info('CONNECTION ON OPENED')
		
	def connection_on_closed(self,connection,**kw):
		logging.info('CONNECTION ON CLOSED')
		
	def connection_on_message(self,connection,message):
		logging.info('CONNECTION ON MESSAGE')
		logging.info(message)
		self.sendEventToPeer('getSdp',json.loads(str(message)))
		"""message = json.loads(str(message))
		if 'plugindata' in message and 'jsep' in message:
			logging.info(message)
			#logging.info(kw['sdp'])
			self.sendEventToPeer('getSdp', message)
			#logging.info(kw['jsep'])
		"""
	#SESSION
	def session_on_connected(self,session,**kw):
		logging.info('SESSION ON OPENED')
	def session_on_disconnected(self,session,**kw):
		logging.info('SESSION ON CLOSED')
	def session_on_message(self,session,**kw):
		logging.info('SESSION ON MESSAGE')
		logging.info(kw ['message'])
		self.sendEventToPeer('getSdp',kw['message'])
		
	def session_on_plugin_attached(self,session,**kw):
		logging.info('SESSION ON PLUGIN ATTACHED')
		logging.info(kw)
		#self.sendEventToPeer('getSdp', kw['plugin'])

	def session_on_plugin_detached(self,session,**kw):
		logging.info('SESSION ON PLUGIN DETACHED')
	
	
	#PLUGIN
	def streamingPlugin_on_message(self,plugin,**kw):
		#if 'message' in kw:
		#	logging.info(kw['message'])
		#logging.info(kw['message'])
		if 'sdp' in kw:
			logging.info(kw['sdp'])
			self.sendEventToPeer('getSdp',kw['sdp'])
		
	
	def streamingPlugin_on_attached(self,plugin,**kw):
		logging.info('STREAMINGPLUGIN ON ATTACHED')
	
	def streamingPlugin_on_detached(self,plugin,**kw):
		logging.info('STREAMINGPLUGIN ON DETACHED')
	
	def streamingPlugin_on_webrtcup(self,plugin,**kw):
		logging.info('STREAMINGPLUGIN ON WEBRTCUP')
		#logging.info(kw ['message'])
		#self.sendEventToPeer('getSdp',kw['message'])
	
	def streamingPlugin_on_hangup(self,plugin,**kw):
		logging.info('STREAMINGPLUGIN ON HANGUP')
		logging.info(kw ['message'])
		self.sendEventToPeer('getSdp',kw['message'])
	
	def start(self):
		
		sem = threading.Semaphore(0)
		
		self.streamingPlugin = StreamingPlugin()
		self.session = Session('ws://127.0.0.1:8188', secret='d5faa25fe8e3438d826efb1cd3369a50')
		
		@self.session.on_plugin_attached.connect
		def receive_data(sender, **kw):
			logging.info('PLUGIN ENGANCHADO')
			sem.release()
		
		
		#CONNECTION
		#self.session.cxn_cls
		#
		#SIGNALS
		#
		# Signal fired when `Connection` has been established.
	    #	on_opened = blinker.Signal()
		self.session.cxn_cls.on_opened.connect(self.connection_on_opened)
		
		#
	    # Signal fired when `Connection` has been closed.
	    #	on_closed = blinker.Signal()
		self.session.cxn_cls.on_closed.connect(self.connection_on_closed)
		
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
		self.session.on_connected.connect(self.session_on_connected)
		
		#
		# Signal fired when `Session` has been disconnected.
		#	on_disconnected = blinker.Signal()
		self.session.on_disconnected.connect(self.session_on_disconnected)
		
		#
		# Signal fired when a `Session` level message is received.
		#	on_message = blinker.Signal()
		self.session.on_message.connect(self.session_on_message)
	
		#
		# Signal fired when a `Session` `Plugin` been attached.
		#	on_plugin_attached = blinker.Signal()
		self.session.on_plugin_attached.connect(self.session_on_plugin_attached)

		#
		# Signal fired when a `Session` `Plugin` been detached.
		#	on_plugin_detached = blinker.Signal()
		self.session.on_plugin_detached.connect(self.session_on_plugin_detached)
	
		##
		
		
		#PLUGIN
		#self.streamingPlugin
		#
		#SIGNALS
		#
		# Signal fired when a `Plugin` is attached to a `Session`.
		#	on_attached = blinker.Signal()
		self.streamingPlugin.on_attached.connect(self.streamingPlugin_on_attached)
		
		#
		# Signal fired when a `Plugin` is attached to a `Session`.
		#	on_detached = blinker.Signal()
		self.streamingPlugin.on_detached.connect(self.streamingPlugin_on_detached)
		
		#
		# Signal fired when a `Plugin` receives a message.
		#	on_message = blinker.Signal()
		self.streamingPlugin.on_message.connect(self.streamingPlugin_on_message)
		#
		
		# Signal fired when webrtc for a `Plugin` has been setup.
		#	on_webrtcup = blinker.Signal()
		self.streamingPlugin.on_webrtcup.connect(self.streamingPlugin_on_webrtcup)
		
		
		#
		# Signal fired when webrtc session for a `Plugin` has been torn down.
		#	on_hangup = blinker.Signal()
		self.streamingPlugin.on_hangup.connect(self.streamingPlugin_on_hangup)
		
		##
		
		self.session.register_plugin(self.streamingPlugin);
		self.session.connect();
		
		
		self.sessionKa = KeepAlive(self.session)
		self.sessionKa.daemon = True
		self.sessionKa.start()
		
		"""
		self.session.cxn.on_message.send(self.recv_message)
		"""
			
		sem.acquire()


		

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
		logging.info('MANDA')
