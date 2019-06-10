import logging


import tornado.ioloop
import tornado.web
import tornado.gen
import time
import tornado

import threading
from astroprint.camera import cameraManager
from flask import abort


class VideoStreamHandler(tornado.web.RequestHandler):

	def on_finish(self):
		logging.info('on_finish')

	def on_connection_close(self):
		logging.info('on_connection_close')

		cameraMgr = cameraManager()
		cameraMgr.removeLocalPeerReq(self.id)

	@tornado.web.asynchronous
	@tornado.gen.coroutine
	def get(self):

		if cameraManager().startLocalVideoSession('local'):

			logging.info('N')

			cameraMgr = cameraManager()

			ioloop = tornado.ioloop.IOLoop.current()

			self.id = cameraMgr.addLocalPeerReq()

			self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
			self.set_header('Connection', 'close')
			self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--boundarydonotcross')
			self.set_header('Expires', 'Mon, 3 Jan 2100 12:34:56 GMT')
			self.set_header('Pragma', 'no-cache')
			self.set_header('Session_id', self.id)

			self.served_image_timestamp = time.time()
			my_boundary = "--boundarydonotcross\n"

			stillStreaming = True

			'''def frameFlushedCb():
				logging.info('frameFlushedCb')
				self.sendNextFrame = True

			self.sendNextFrame = True'''

			from threading import Thread

			while stillStreaming:
				#if self.sendNextFrame:
				#logging.info('W')
				stillStreaming = cameraMgr.localSessionAlive(self.id)
				logging.info('still streaming peer %s: %s' % (self.id,stillStreaming))
				img = cameraMgr.getFrame(self.id)
				interval = 1/25
				#logging.info('D')
				if img:# and self.served_image_timestamp + interval < time.time():
					#logging.info('C')
					self.write(my_boundary)
					self.write("Content-type: image/jpeg\r\n")
					self.write("Content-length: %s\r\n\r\n" % len(img))
					self.write(str(img))
					self.served_image_timestamp = time.time()
					self.sendNextFrame = False
					#yield tornado.gen.Task(Thread(target = self.flush(callback=frameFlushedCb)).start())
					yield tornado.gen.Task(self.flush)
				#else:
					#logging.info('B')
				#	yield tornado.gen.Task(ioloop.add_timeout, ioloop.time() + interval)
				#else:
				#	logging.info('AD')
				#	yield tornado.gen.Task(ioloop.add_timeout, ioloop.time() + interval)
		else:
			logging.info('O')
			abort(500)
