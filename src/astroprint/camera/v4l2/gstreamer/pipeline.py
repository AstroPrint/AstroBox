# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import json
import time

from multiprocessing import Process, Queue, Event

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
		self._process = Process(
			target= startPipelineProcess,
			args= (
				device,
				tuple([int(x) for x in size.split('x')]),
				source,
				encoding,
				onListeningEvent,
				self._reqQ,
				self._respQ,
			)
		)
		self._process.start()
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

	def startVideo(self, doneCallback = None):
		if self._process and self._process.exitcode is None:
			self._reqQ.put({'action': 'startVideo'})
			resp = self._respQ.get()
			return resp if resp else False

		else:
			self._logger.warn('startVideo ignored. No Process is running')
			resp = False

		if doneCallback:
			doneCallback(resp)

	def stopVideo(self, doneCallback = None):
		if self._process and self._process.exitcode is None:
			self._reqQ.put( {'action': 'stopVideo'} )
			resp = self._respQ.get()
			return resp if resp else False

		else:
			self._logger.warn('stopVideo ignored. No Process is running')
			resp = False

		if doneCallback:
			doneCallback(resp)

	def takePhoto(self, doneCallback, text=None):
		if self._process and self._process.exitcode is None:
			if text is not None:
				self._reqQ.put( {'action': 'takePhoto', 'data': {'text': text}} )
			else:
				self._reqQ.put( {'action': 'takePhoto', 'data': None} )

			resp = self._respQ.get()

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

		else:
			self._logger.warn('takePhoto ignored. No Process is running')
			doneCallback(None)

	def isVideoPlaying(self):
		if self._process and self._process.exitcode is None:
			self._reqQ.put( {'action': 'isVideoPlaying'} )
			resp = self._respQ.get()
			return resp if resp else False

		else:
			self._logger.warn('isVideoPlaying ignored. No Process is running')
			return False

	def stop(self):
		if self._process and self._process.exitcode is None:
			self._reqQ.put( {'action': 'shutdown'} )
			self._process.join()
			self._reqQ.close()
			self._respQ.close()
			self._process = None
