import logging

import tornado.ioloop
import tornado.web
import tornado.gen
import datetime

from astroprint.camera import cameraManager

class VideoStreamHandler(tornado.web.RequestHandler):
	def initialize(self,access_validation):
		self._logger = logging.getLogger(__name__)
		self.cameraMgr = cameraManager()
		self.id = self.cameraMgr.addLocalPeerReq()
		self._access_validation = access_validation

	def on_finish(self):
		self._logger.debug('on_finish id - %s' % self.id)

	def on_connection_close(self):
		self._logger.debug('on_connection_close id - %s' % self.id)

		self.cameraMgr.removeLocalPeerReq(self.id)

	@tornado.web.asynchronous
	@tornado.gen.coroutine
	def get(self):
		try:
			self._access_validation(self.request)

			self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
			self.set_header('Connection', 'close')
			self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--boundarydonotcross')
			self.set_header('Pragma', 'no-cache')
			self.set_header('Cache-Control', 'no-cache')

			my_boundary = "--boundarydonotcross\n"

			stillStreaming = True

			self.sendNextFrame = True

			while stillStreaming:

				stillStreaming = self.cameraMgr.localSessionAlive(self.id)

				img = self.cameraMgr.getFrame(self.id)

				if img:
					self.write(my_boundary)
					self.write("Content-type: image/jpeg\r\n")
					self.write("Content-length: %s\r\n\r\n" % len(img))
					self.write(str(img))
					yield tornado.gen.Task(self.flush)
				else:
					stillStreaming = None

			self.flush()
			self.finish()

		except Exception as e:
			self._logger.error('local video streaming: %s' % e, exc_info=True)
			raise(e)
