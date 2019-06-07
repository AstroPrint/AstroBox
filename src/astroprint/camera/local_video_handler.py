import logging


import tornado.ioloop
import tornado.web
import tornado.gen
import time
import tornado

import threading
from astroprint.camera import cameraManager

class VideoStreamHandler(tornado.web.RequestHandler):

	@tornado.web.asynchronous
	@tornado.gen.coroutine
	def get(self):

		logging.info('N')

		cameraMgr = cameraManager()

		ioloop = tornado.ioloop.IOLoop.current()

		self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
		self.set_header('Connection', 'close')
		self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--boundarydonotcross')
		self.set_header('Expires', 'Mon, 3 Jan 2100 12:34:56 GMT')
		self.set_header('Pragma', 'no-cache')

		self.served_image_timestamp = time.time()
		my_boundary = "--boundarydonotcross\n"


		self.id = cameraMgr.addLocalPeerReq()

		while True:
			logging.info('W')
			img = cameraMgr.getFrame(self.id)
			interval = 1/25
			logging.info('D')
			if img and self.served_image_timestamp + interval < time.time():
				logging.info('C')
				self.write(my_boundary)
				self.write("Content-type: image/jpeg\r\n")
				self.write("Content-length: %s\r\n\r\n" % len(img))
				self.write(str(img))
				self.served_image_timestamp = time.time()
				yield tornado.gen.Task(self.flush)
			else:
				logging.info('B')
				yield tornado.gen.Task(ioloop.add_timeout, ioloop.time() + interval)

