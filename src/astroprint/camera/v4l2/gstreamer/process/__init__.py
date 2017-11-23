# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import sys

from threading import Thread, Event, Condition

from .pipelines import pipelineFactory, InvalidGStreamerPipelineException

def startPipelineProcess(device, size, rotation, source, encoding, onListeningEvent, errorState, procPipe, debugLevel=0):
	from gi.repository import GObject

	GObject.threads_init()
	mainLoop = GObject.MainLoop()

	logger = logging.getLogger(__name__ + ':processLoop')
	interface = None

	def onFatalError(details):
		if interface:
			interface.sendResponse(0, {'error': 'fatal_error', 'details': details})
		else:
			#There was a fatal error during the creation of the pipeline, interface has not even been created
			logger.error('Fatal error creating pipeline: %s' % details)
			raise SystemExit(-1)

	try:
		pipeline = pipelineFactory(device, size, rotation, source, encoding, onFatalError, mainLoop, debugLevel)
	except InvalidGStreamerPipelineException as e:
		logger.error(e)
		raise SystemExit(-1)

	interface = processInterface(pipeline, procPipe, mainLoop, onListeningEvent)

	try:
		interface.start()
		logger.debug('Pipeline process started')
		mainLoop.run()

	except KeyboardInterrupt, SystemExit:
		mainLoop.quit()

	except Exception as e:
		mainLoop.quit()
		raise e

	finally:
		if interface.isAlive():
			interface.stop()

		interface.join()

		if not onListeningEvent.is_set():
			errorState.value = True
			onListeningEvent.set()

		logger.debug('Pipeline process ended')


class processInterface(Thread):
	RESPONSE_EXIT = -1000
	RESPONSE_ASYNC = -1001

	def __init__(self, pipeline, procPipe, mainLoop, onListeningEvent):
		self._pipeline = pipeline
		self._parentConn, self._processConn = procPipe
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
		if not self._pipeline.setToPlayAndWait():
			self._pipeline.tearDown()
			self._pipeline = None
			raise SystemExit(-1)

		self._onListeningEvent.set() # Inform the client that we're ready
		self._onListeningEvent = None # unref

		while not self._stopped:
			self._logger.debug('waiting for commands...')
			command = self._processConn.recv()
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

		self._pipeline.tearDown()
		self._pipeline = None

	def _isVideoPlayingAction(self, reqId):
		self.sendResponse(reqId, self._pipeline.isVideoStreaming())
		return self.RESPONSE_ASYNC

	def _startVideoAction(self, reqId):

		def doneCb(success):
			self.sendResponse(reqId, success)

		self._pipeline.playVideo(doneCb)

		return self.RESPONSE_ASYNC

	def _stopVideoAction(self, reqId):

		def doneCb(success):
			self.sendResponse(reqId, success)

		self._pipeline.stopVideo(doneCb)

		return self.RESPONSE_ASYNC

	def _takePhotoAction(self, reqId, text=None):

		def doneCb(photo):
			if not photo:
				self.sendResponse(reqId, None)
			else:
				self.sendResponse(reqId, photo, raw= True, b64encode= True)

		self._pipeline.takePhoto(doneCb, text)

		return self.RESPONSE_ASYNC

	def _shutdownAction(self, reqId):
		return self.RESPONSE_EXIT

	def sendResponse(self, reqId, resp, raw= False, b64encode= False):
		if raw:
			if b64encode:
				from base64 import b64encode
				resp = b64encode(resp)

		response = (reqId, resp)

		with self._sendCondition:
			self._processConn.send( response )
			if self._logger.isEnabledFor(logging.DEBUG):
				if sys.getsizeof(resp) > 50:
					dataStr = "(%d, %d bytes)" % (reqId, sys.getsizeof(resp))
				else:
					dataStr = repr(response)

				self._logger.debug('Sent: [ %s ]' % repr(dataStr) )

	def stop(self):
		self._stopped = True
