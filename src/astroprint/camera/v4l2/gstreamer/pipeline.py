# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import json
import time
import sys

from multiprocessing import Process, Queue, Event
from threading import Thread, Condition, current_thread

from blinker import signal

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from .process import startPipelineProcess

class AstroPrintPipeline(object):
	def __init__(self, device, size, source, encoding):
		self._logger = logging.getLogger(__name__)
		onListeningEvent = Event()
		self._reqQ = Queue()
		self._respQ = Queue()
		self._pendingReqs = {}
		self._lastReqId = 0
		self._sendCondition = Condition()
		self._process = Process(
			target= startPipelineProcess,
			args= (
				device,
				tuple([int(x) for x in size.split('x')]),
				source.lower(),
				encoding.lower(),
				onListeningEvent,
				self._reqQ,
				self._respQ,
			)
		)
		self._process.start()

		self._responseListener = ProcessResponseListener(self._respQ, self._onProcessResponse)
		self._responseListener.start()

		onListeningEvent.wait()

	"""def run(self):

		self._process = subprocess.Popen([
			'/home/pi/development/gst-ap-controller/gst-ap',
			'--device', self._device,
			'--width', self._size[0],
			'--height', self._size[1],
			'--source', self._source.lower(),
			'--encoding', self._encoding
		], stdin=subprocess.PIPE, stdout=subprocess.PIPE)


		ready = self._process.stdout.readline().strip() == 'ready'

		if ready:
			self._onListeningEvent.set()
			self._onListeningEvent = None

		self._process.wait()

		if self._process.wait() != 0:
			self._logger.error('GstAstroPrint terminated with error %d' % self._process.returncode)

			message = 'Fatal error occurred in video streaming (%d)' % self._process.returncode

			#signaling for remote peers
			manage_fatal_error_webrtc = signal('manage_fatal_error_webrtc')
			manage_fatal_error_webrtc.send('cameraError', message= message)

			#event for local peers
			eventManager().fire(Events.GSTREAMER_EVENT, {
				'message': message
			})

			try:
				self._logger.info("Trying to get list of formats supported by your camera...")
				self._logger.info(subprocess.Popen("v4l2-ctl --list-formats-ext -d %s" % str(self._device), shell=True, stdout=subprocess.PIPE).stdout.read())

			except:
				self._logger.error("Unable to retrieve supported formats")

			if settings().get(["camera", "graphic-debug"]):
				try:
					gst.debug_bin_to_dot_file (self._pipeline, gst.DebugGraphDetails.ALL, "fatal-error")
					self._logger.info( "Gstreamer's pipeline dot file created: %s/fatal-error.dot" % os.getenv("GST_DEBUG_DUMP_DOT_DIR") )

				except:
					self._logger.error("Graphic diagram can not created")

		self._process = None"""

	def _onProcessResponse(self, id, data):
		if id in self._pendingReqs:
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
		with self._sendCondition:
			self._lastReqId += 1
			id = self._lastReqId
			self._pendingReqs[id] = callback
			self._reqQ.put( (id, data) )
			self._logger.debug('Sent request %d to process [ %s ]' % (id, repr(data)))

	def startVideo(self, doneCallback = None):
		if self._process and self._process.exitcode is None:
			self._sendReqToProcess({'action': 'startVideo'}, doneCallback)

		else:
			self._logger.warn('startVideo ignored. No Process is running')
			if doneCallback:
				doneCallback(False)

	def stopVideo(self, doneCallback = None):
		if self._process and self._process.exitcode is None:
			self._sendReqToProcess({'action': 'stopVideo'}, doneCallback)

		else:
			self._logger.warn('stopVideo ignored. No Process is running')
			if doneCallback:
				doneCallback(False)

	def takePhoto(self, doneCallback, text=None):
		if self._process and self._process.exitcode is None:
			def posprocesing(resp):
				if resp:
					if 'error' in resp:
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
				self._sendReqToProcess({'action': 'takePhoto', 'data': {'text': text}}, posprocesing)
			else:
				self._sendReqToProcess({'action': 'takePhoto', 'data': None}, posprocesing)

		else:
			self._logger.warn('takePhoto ignored. No Process is running')
			doneCallback(False)

	def isVideoPlaying(self, doneCallback):
		if self._process and self._process.exitcode is None:
			self._sendReqToProcess({'action': 'isVideoPlaying'}, doneCallback)

		else:
			self._logger.warn('isVideoPlaying ignored. No Process is running')
			doneCallback(False)

	def stop(self):
		if self._process and self._process.exitcode is None:
			self._sendReqToProcess({'action': 'shutdown'})
			self._process.join()
			self._process = None
			self._reqQ.close()
			self._respQ.close()
			self._responseListener.stop()

			#It's possible that stop is called as a result of a response which is
			#executed in the self._responseListener Thread. You can't join your own thread!
			if current_thread() != self._responseListener:
				self._responseListener.join()

			self._responseListener = None

#
# Thread to listen for incoming responses from the process
#

class ProcessResponseListener(Thread):
	def __init__(self, responseQueue, onNewResponse):
		super(ProcessResponseListener, self).__init__()
		self._queue = responseQueue
		self._stopped = False
		self._onNewResponse = onNewResponse

	def run(self):
		while not self._stopped:
			response = self._queue.get()

			if not self._stopped:
				if response:
					try:
						id, data = response

						self._onNewResponse(id, data)

					except Exception as e:
						self._logger.error("Error unpacking gstreamer process response", exc_info= True)

	def stop(self):
		self._stopped = True
