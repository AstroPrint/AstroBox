# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import json
import time
import sys
import os
import signal
import subprocess

from multiprocessing import Process, Event, Pipe, Value
from threading import Thread, Condition, current_thread

from blinker import signal as blinkerSignal

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from .process import startPipelineProcess

class AstroPrintPipeline(object):
	def __init__(self, device, size, rotation, source, encoding, onFatalError):
		self._logger = logging.getLogger(__name__)
		self._parentConn, self._processConn = Pipe(True)
		self._pendingReqs = {}
		self._lastReqId = 0
		self._device = device
		self._rotation = rotation
		self._source = source.lower()
		self._encoding = encoding.lower()
		self._size = tuple([int(x) for x in size.split('x')])
		self._sendCondition = Condition()
		self._onFatalError = onFatalError
		self._responseListener = ProcessResponseListener(self._parentConn, self._onProcessResponse)
		self._responseListener.start()
		self._process = None
		self._listening = False

	def __del__(self):
		self._logger.debug('Pipeline Process Controller removed')

	def _kill(self):
		if self._process:
			try:
				os.kill(self._process.pid, signal.SIGKILL)
				self._process.join()
			except OSError as e:
				# error 3: means the pid is not valid, so the process has been killed
				if e.errno != 3:
					raise e

			self._process = None

	def startProcess(self):
		if self._process:
			# This should almost never happen (but it does)
			# Make sure the previous process is killed before a new one is started
			self._logger.warn("A previous process was still running, killing it")
			self._kill()

		onListeningEvent = Event()
		errorState = Value('b', False) #If True, it means the process had an error while starting
		self._listening = False

		self._process = Process(
			target= startPipelineProcess,
			args= (
				self._device,
				self._size,
				self._rotation,
				self._source,
				self._encoding,
				onListeningEvent,
				errorState,
				( self._parentConn, self._processConn ),
				settings().getInt(['camera', 'debug-level'])
			)
		)
		self._process.daemon = True
		self._process.start()
		if onListeningEvent.wait(20.0):
			if errorState.value:
				self._logger.error('Pipeline Failed to start.')
				self._kill()
				self._logger.debug('Pipeline Process killed.')

			else:
				self._logger.debug('Pipeline Process Started.')
				self._listening = True

		else:
			self._logger.debug('Timeout while waiting for pipeline process to start')
			self._kill()

	def stopProcess(self):
		if self._process:
			if self._listening:
				self._sendReqToProcess({'action': 'shutdown'})
				self._process.join(2.0) #Give it two seconds to exit and kill otherwise

			if self._process.exitcode is None:
				self._logger.warn('Process did not shutdown properly. Terminating...')
				self._process.terminate()
				self._process.join(2.0) # Give it another two secods to terminate, otherwise kill
				if self._process and self._process.exitcode is None:
					self._logger.warn('Process did not terminate properly. Sending KILL signal...')
					self._kill()

			self._logger.debug('Process terminated')
			self._process = None

	@property
	def processRunning(self):
		return self._process and self._process.is_alive()

	def stop(self):
		self._responseListener.stop()
		self.stopProcess()

		#It's possible that stop is called as a result of a response which is
		#executed in the self._responseListener Thread. You can't join your own thread!
		if current_thread() != self._responseListener:
			self._responseListener.join()

		self._responseListener = None

	def startVideo(self, doneCallback = None):
		self._sendReqToProcess({'action': 'startVideo'}, doneCallback)

	def stopVideo(self, doneCallback = None):
		self._sendReqToProcess({'action': 'stopVideo'}, doneCallback)

	def isVideoPlaying(self, doneCallback):
		self._sendReqToProcess({'action': 'isVideoPlaying'}, doneCallback)

	def takePhoto(self, doneCallback, text=None):
		def postprocesing(resp):
			if resp:
				if isinstance(resp, dict) and 'error' in resp:
					self._logger.error('Error during photo capture: %s' % resp['error'])
					doneCallback(None)
				else:
					from base64 import b64decode
					try:
						doneCallback(b64decode(resp))
					except TypeError as e:
						self._logger.error('Invalid returned photo. Received. Error: %s' % e)
						doneCallback(None)

			else:
				doneCallback(None)

		if text is not None:
			self._sendReqToProcess({'action': 'takePhoto', 'data': {'text': text}}, postprocesing)
		else:
			self._sendReqToProcess({'action': 'takePhoto', 'data': None}, postprocesing)

	def _onProcessResponse(self, id, data):
		if id is 0: # this is a broadcast, likely an error. Inform all pending requests
			self._logger.warn('Broadcasting error to ALL pending requests [ %s ]' % repr(data))
			if self._pendingReqs:
				for cb in self._pendingReqs.values():
					if cb:
						cb(data)

			if data and 'error' in data and data['error'] == 'fatal_error':
				message = 'Fatal error occurred in video streaming (%s)' % data['details'] if 'details' in data else 'unkonwn'

				#signaling for remote peers
				manage_fatal_error_webrtc = blinkerSignal('manage_fatal_error_webrtc')
				manage_fatal_error_webrtc.send(self, message= message)

				#event for local peers
				eventManager().fire(Events.GSTREAMER_EVENT, {
					'message': message
				})

				try:
					self._logger.info("Trying to get list of formats supported by your camera...")
					self._logger.info(subprocess.Popen("v4l2-ctl --list-formats-ext -d %s" % str(self._device), shell=True, stdout=subprocess.PIPE).stdout.read())

				except:
					self._logger.error("Unable to retrieve supported formats")

				#shutdown the process
				self._pendingReqs = {}
				self._onFatalError()

		elif id in self._pendingReqs:
			try:
				callback = self._pendingReqs[id]
				if callback:
					callback(data)

				del self._pendingReqs[id]

				if self._logger.isEnabledFor(logging.DEBUG):
					if sys.getsizeof(data) > 50:
						dataStr = "%d bytes" % sys.getsizeof(data)
					else:
						dataStr = repr(data)

					self._logger.debug('Response for %d handled [ %s ]' % (id, dataStr))

			except Exception:
				self._logger.error("Problem executing callback response", exc_info= True)

		else:
			self._logger.error("There's no pending request for response %d" % id)

	def _sendReqToProcess(self, data, callback= None):
		if self.processRunning:
			with self._sendCondition:
				if self._listening:
					self._lastReqId += 1
					id = self._lastReqId
					self._pendingReqs[id] = callback
					self._parentConn.send( (id, data) )
					self._logger.debug('Sent request %d to process [ %s ]' % (id, repr(data)))

				else:
					self._logger.debug('Process not listening. There was a problem while starting it.')
					if callback:
						callback({'error': 'not_listening', 'details': 'The process is not currently listening to requests'})

		else:
			self._logger.debug('Process not running. Trying to restart')
			self.startProcess()
			if self.processRunning:
				self._sendReqToProcess(data, callback)

			else:
				self._logger.error('Unable to re-start pipeline process.')
				if callback:
					callback({'error': 'no_process', 'details': 'Unable to re-start process'})

#
# Thread to listen for incoming responses from the process
#

class ProcessResponseListener(Thread):
	def __init__(self, parentConn, onNewResponse):
		super(ProcessResponseListener, self).__init__()
		self._logger = logging.getLogger(__name__ + ':ProcessResponseListener')
		self._parentConn = parentConn
		self._stopped = False
		self._onNewResponse = onNewResponse

	def run(self):
		while not self._stopped:
			try:
				while not self._parentConn.poll(1.0):
					if self._stopped:
						return
				response = self._parentConn.recv()
			except IOError:
				self._logger.debug('Process closed its connection. Stoping ProcessResponseListener')
				return

			try:
				id, data = response

				self._onNewResponse(id, data)

			except Exception:
				self._logger.error("Error unpacking gstreamer process response", exc_info= True)

	def stop(self):
		self._stopped = True
