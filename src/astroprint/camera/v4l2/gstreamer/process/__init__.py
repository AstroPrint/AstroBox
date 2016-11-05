# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import sys

from threading import Thread, Event, Condition

from .pipelines import pipelineFactory, InvalidGStreamerPipelineException

def startPipelineProcess(device, size, source, encoding, onListeningEvent, reqQ, respQ, debugLevel=0):
	from gi.repository import GObject

	GObject.threads_init()
	mainLoop = GObject.MainLoop()

	logger = logging.getLogger(__name__ + ':processLoop')

	try:
		pipeline = pipelineFactory(device, size, source, encoding, mainLoop, debugLevel)
	except InvalidGStreamerPipelineException as e:
		import sys

		logger.error(e)
		onListeningEvent.set()
		sys.exit(-1)

	interface = processInterface(pipeline, reqQ, respQ, mainLoop, onListeningEvent)

	try:
		interface.start()
		logger.info('Pipeline process started')
		mainLoop.run()
		logger.info('Pipeline process ended')

	except KeyboardInterrupt, SystemExit:
		mainLoop.quit()

	except Exception as e:
		mainLoop.quit()
		raise e

	finally:
		if interface.isAlive():
			interface.stop()

		interface.join()

		respQ.close()
		reqQ.close()

		if not onListeningEvent.is_set():
			onListeningEvent.set()

class processInterface(Thread):
	RESPONSE_EXIT = -1000
	RESPONSE_ASYNC = -1001

	def __init__(self, pipeline, reqQ, respQ, mainLoop, onListeningEvent):
		self._pipeline = pipeline
		self._reqQ = reqQ
		self._respQ = respQ
		self._sendCondition = Condition()
		self._onListeningEvent = onListeningEvent
		self._mainLoop = mainLoop
		self._logger = logging.getLogger(__name__+':processInterface')

		super(processInterface, self).__init__()

		self._actionMap = {
			'isVideoPlaying': self._isVideoPlayingAction,
			'startVideo': self._startVideoAction,
			'stopVideo': self._stopVideoAction,
			'takePhoto': self._takePhotoAction,
			'shutdown': self._shutdownAction
		}

		self.daemon = True
		self._stopped = False

	def run(self):
		self._onListeningEvent.set() # Inform the client that we're ready
		self._onListeningEvent = None # unref
		while not self._stopped:
			self._logger.debug('waiting for commands...')
			command = self._reqQ.get()
			if self._stopped:
				break

			self._logger.debug('Recieved: %s' % repr(command))
			if command:
				id, payload = command
				if payload['action'] in self._actionMap:
					if 'data' in payload:
						kargs = payload['data'] or {}
					else:
						kargs = {}

					kargs['reqId'] = id
					resp = self._actionMap[payload['action']](**kargs)

				else:
					resp = {
						'error': 'command_not_found',
						'details': payload
					}

			else:
				resp = {
					'error': 'invalid_command',
					'details': line
				}

			if resp is self.RESPONSE_EXIT:
				break

		self._pipeline = None
		self._mainLoop.quit()

	def _isVideoPlayingAction(self, reqId):
		self._sendResponse(reqId, self._pipeline.isVideoStreaming())
		return self.RESPONSE_ASYNC

	def _startVideoAction(self, reqId):

		def doneCb(success):
			self._sendResponse(reqId, success)

		self._pipeline.playVideo(doneCb)

		return self.RESPONSE_ASYNC

	def _stopVideoAction(self, reqId):

		def doneCb(success):
			self._sendResponse(reqId, success)

		self._pipeline.stopVideo(doneCb)

		return self.RESPONSE_ASYNC

	def _takePhotoAction(self, reqId, text=None):

		def doneCb(photo):
			if not photo:
				self._sendResponse(reqId, None)
			else:
				self._sendResponse(reqId, photo, raw= True, b64encode= True)

		self._pipeline.takePhoto(doneCb, text)

		return self.RESPONSE_ASYNC

	def _shutdownAction(self, reqId):
		self._pipeline.tearDown()
		return self.RESPONSE_EXIT

	def _sendResponse(self, reqId, resp, raw= False, b64encode= False):
		if raw:
			if b64encode:
				from base64 import b64encode
				resp = b64encode(resp)


		response = (reqId, resp)

		with self._sendCondition:
			self._respQ.put( response )
			if self._logger.isEnabledFor(logging.DEBUG):
				if sys.getsizeof(resp) > 50:
					dataStr = "(%d, %d bytes)" % (reqId, sys.getsizeof(resp))
				else:
					dataStr = repr(response)

				self._logger.debug('Sent: [ %s ]' % repr(dataStr) )

	def stop(self):
		self._stopped = True
