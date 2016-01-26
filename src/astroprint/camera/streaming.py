import astroprint.webrtc.janus

class StreamingPlugin(janus.Plugin):
    name = 'janus.plugin.streaming'


class WebRTC(object):
	def __init__(self):
		self.streamingPlugin = StreamingPlugin();
		self.session = None

	def startJanus(self):
		#Start janus command here

		self.session = janus.Session('ws://127.0.0.1:8088', secret='astroprint_janus')
		self.session.register_plugin(self.streamingPlugin);
		self.session.connect();

		self.sessionKa = janus.KeepAlive(self.session)
    	self.sessionKa.daemon = True
    	self.sessionKa.start()

	def stopJanus(self):
		#stop the keepalive worker
		self.sessionKa.stop()
		self.sessionKa.join()
		self.sessionKa = None

		#kill the current session
		self.session.unregister_plugin(self.streamingPlugin)
		self.session.disconnect()
		self.session = None

		#Stop janus server