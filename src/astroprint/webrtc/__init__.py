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

from astroprint.webrtc.janus import Plugin, Session, KeepAlive

class WebRtc(object):
	def __init__(self):
		self._connectedPeers = {}
		self._logger = logging.getLogger(__name__)
		self._peerCondition = threading.Condition()
		self._process = None

	def startPeerSession(self):
		with self._peerCondition:
			if len(self._connectedPeers.keys()) == 0:
				self.startJanus()

			peer = ConnectionPeer()

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
			peer = self._connectedPeers[sessionId]

		except KeyError:
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None

		if peer:
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'list'})	
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'watch','id':2})

	def setSessionDescriptionAndStart(self, sessionId, data):
		
		try:
			peer = self._connectedPeers[sessionId]
			
		except KeyError:
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None

		if peer:
			self._connectedPeers[sessionId].streamingPlugin.set_session_description(data['type'],data['sdp'])
			#preparing state
			self._connectedPeers[sessionId].streamingPlugin.send_message({'request':'start'})
			#starting state


	def tickleIceCandidate(self, sessionId, candidate, sdp_mid, sdp_mline_index):
		
		try:
			peer = self._connectedPeers[sessionId]

		except KeyError:
			self._logger.warning('Peer with session [%s] is not found' % sessionId)
			peer = None

		if peer:
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

class ConnectionPeer(object):
	def __init__(self):
		self.session = None
		self.sessionKa = None
		self.id = None
		self.streamingPlugin = None

	def start(self):
		
		sem = threading.Semaphore(0)
		
		self.streamingPlugin = StreamingPlugin()
		self.session = Session('ws://127.0.0.1:8188', secret='d5faa25fe8e3438d826efb1cd3369a50')
		
		@self.session.on_plugin_attached.connect
		def receive_data(sender, **kw):
			sem.release()
	
		@self.session.on_message.connect
		def send_response(sender, **kw):
			logging.info('MENSAJE RECIBIDO')
			if kw['plugindata']:
				logging.info('MENSAJE')
				logging.info(kw[''])
		
		
		self.session.register_plugin(self.streamingPlugin);
		self.session.connect();
		
		self.sessionKa = KeepAlive(self.session)
		self.sessionKa.daemon = True
		self.sessionKa.start()
		
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