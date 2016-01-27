import astroprint.webrtc.janus
import subprocess

class StreamingPlugin(astroprint.webrtc.janus.Plugin):
	name = 'janus.plugin.streaming'


class WebRtc(object):
    
	def __init__(self):
		self.streamingPlugin = StreamingPlugin();
		self.session = None
		self._process = None

	def startJanus(self):
		#Start janus command here
		args = ['/opt/janus/bin/./janus']

		try:
			self._process = subprocess.Popen(
		    	args
			)
		
		except Exception, error:
			self._logger.error("Error initiating janus process: %s" % str(error))
			self._process = None
        
        ##if self._process
            ##

		self.session = astroprint.webrtc.janus.Session('ws://127.0.0.1:8088', secret='astroprint_janus')
		self.session.register_plugin(self.streamingPlugin);
		self.session.connect();

		self.sessionKa = astroprint.webrtc.janus.KeepAlive(self.session)
		self.sessionKa.daemon = True
		self.sessionKa.start()

	def stopJanus(self):
		#stop the keepalive worker
		self._process.kill()
        
		self.sessionKa.stop()
		self.sessionKa.join()
		self.sessionKa = None

		#kill the current session
		self.session.unregister_plugin(self.streamingPlugin)
		self.session.disconnect()
		self.session = None

		#Stop janus server