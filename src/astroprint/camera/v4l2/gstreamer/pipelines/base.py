# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import subprocess
import time

from collections import deque

from threading import Event, Thread

from gi.repository import Gst as gst

from blinker import signal

from octoprint.events import eventManager, Events
from octoprint.settings import settings

#
#  Base Class for GStreamer Pipeline management
#

class GstBasePipeline(object):
	STATE_IDLE = 0
	STATE_PREPARING_STREAMING = 1
	STATE_STREAMING = 2
	STATE_PHOTO = 3

	def __init__(self, manager, device, size):
		self._videoSourceElement = None
		self._videoLogoElement = None
		self._videoSourceCaps = None
		self._teeElement = None
		self._teePadVideoEnc = None
		self._teePadPhoto = None
		self._teePadPhotoText = None
		self._queueVideoElement = None
		self._queuePhotoElement = None
		self._jpegEncElement = None
		self._queuePhotoTextElement = None
		self._jpegTextEncElement = None

		#queue control
		self._videoEncQueueLinked = False
		self._photoQueueLinked = False
		self._photoTextQueueLinked = False

		#probe holders
		self._teePadVideoEncProbe = None

		#Events for synchronization
		self._waitForPhoto = None

		self._device = device
		self._manager = manager
		self._size = tuple(size.split('x'))
		self.state = self.STATE_IDLE

		self._pipeline = gst.Pipeline()
		self._bus = self._pipeline.get_bus()
		self._bus.add_signal_watch()
		self._busOnMessageSignal = self._bus.connect('message', self._onBusMessage)
		self._bus.set_flushing(True)

		self._setupSourceTee()
		self._setupVideoEncodingPipe()
		self._setupPhotoPipe()
		self._setupPhotoTextPipe()

		#Photo Request Queue Management
		self._photoReqs = deque()
		self._photoReqsProcessor = PhotoReqsProcessor(self._photoReqs, self._jpegEncElement,  self._onNoMorePhotoReqs)
		self._photoTextReqs = deque()
		self._photoTextReqsProcessor = PhotoReqsProcessor(self._photoTextReqs, self._jpegTextEncElement, self._onNoMorePhotoTextReqs)

	def __del__(self):
		self._logger.info('Pipeline destroyed')

	def _informClientsOfInterruption(self, message):
		#signaling for remote peers
		manage_fatal_error_webrtc = signal('manage_fatal_error_webrtc')
		manage_fatal_error_webrtc.send('cameraError', message= message)

		#event for local peers
		eventManager().fire(Events.GSTREAMER_EVENT, {
			'message': message or 'Fatal error occurred in video streaming'
		})

	#
	#	 Source Tee Pipeline setup
	#

	def _setupSourceTee(self):
		# VIDEO SOURCE DESCRIPTION
		# #DEVICE 0 (FIRST CAMERA) USING v4l2src DRIVER
		# #(v4l2src: VIDEO FOR LINUX TO SOURCE)

		self._videoSourceElement = gst.ElementFactory.make('v4l2src', 'video_source')
		self._videoSourceElement.set_property("device", '/dev/video%d' % self._device)

		# ASTROPRINT'S LOGO FROM DOWN RIGHT CORNER
		self._videoLogoElement = gst.ElementFactory.make('gdkpixbufoverlay', 'logo_overlay')
		self._videoLogoElement.set_property('location', '/AstroBox/src/astroprint/static/img/astroprint_logo.png')
		self._videoLogoElement.set_property('overlay-width', 150)
		self._videoLogoElement.set_property('overlay-height', 29)

		self._videoLogoElement.set_property('offset-x', int(self._size[0]) - 160)
		self._videoLogoElement.set_property('offset-y', int(self._size[1]) - 30)

		self._videoSourceCaps = gst.ElementFactory.make("capsfilter", "caps_filter")
		self._videoSourceCaps.set_property("caps", gst.Caps.from_string(self._getVideoSourceCaps()))

		# ##
		# TEE COMMAND IN GSTREAMER ABLES TO JOIN NEW OUTPUT
		# QUEUES TO THE SAME SOURCE
		self._teeElement = gst.ElementFactory.make('tee', 'tee')

		self._teePadVideoEnc = self._teeElement.get_request_pad("src_%u")
		self._teePadPhoto = self._teeElement.get_request_pad("src_%u")
		self._teePadPhotoText = self._teeElement.get_request_pad("src_%u")

		#Add Elements to the pipeline
		self._pipeline.add(self._videoSourceElement)
		self._pipeline.add(self._videoLogoElement)
		self._pipeline.add(self._videoSourceCaps)
		self._pipeline.add(self._teeElement)

		#Link Elements
		self._videoSourceElement.link(self._videoSourceCaps)
		self._videoSourceCaps.link(self._videoLogoElement)
		self._videoLogoElement.link(self._teeElement)

	def _tearDownSourceTee(self):
		#unlink element
		#I think unlink happens automatically when removing
		#self._videoLogoElement.unlink(self._teeElement)
		#self._videoSourceCaps.unlink(self._videoLogoElement)
		#self._videoSourceElement.unlink(self._videoSourceCaps)

		#remove elements
		self._pipeline.remove(self._videoSourceElement)
		self._pipeline.remove(self._videoLogoElement)
		self._pipeline.remove(self._videoSourceCaps)
		self._pipeline.remove(self._teeElement)

	def _attachVideoEncodingPipe(self):
		def readyToAttach(success= True):
			if success:
				try:
					videoQueuePad = self._queueVideoElement.get_static_pad("sink")
					gst.Pad.link(self._teePadVideoEnc, videoQueuePad)
					self._videoEncQueueLinked = True
					#self._queueVideoElement.set_state(gst.State.PLAYING)
					return

				except:
					pass

			self._logger.error("Error trying to detach video queue: %s", error)
			self.fatalErrorManager()

		connector = PipelineOperation(self._teePadPhoto, readyToAttach)
		connector.start()

	def _detachVideoEncodingPipe(self, doneCallback= None):

		#Ready callback
		def readyToDetach(success= True):
			if success:
				try:
					self._videoEncQueueLinked = False
					videoQueuePad = self._queueVideoElement.get_static_pad("sink")
					gst.Pad.unlink(self._teePadVideoEnc, videoQueuePad)

					if doneCallback:
						doneCallback(True)

					return

				except:
					pass

			self._logger.error("Error trying to detach video queue: %s", error)
			self.fatalErrorManager()
			if doneCallback:
				doneCallback(False)

		disconnector = PipelineOperation(self._teePadVideoEnc, readyToDetach)
		disconnector.start()

	#
	#	 Photo (no text) pipeline setup
	#

	def _setupPhotoPipe(self):
		self._queuePhotoElement = gst.ElementFactory.make('queue', 'queuephoto')
		self._jpegEncElement = gst.ElementFactory.make('jpegenc', 'jpegenc')
		self._jpegEncElement.set_property('quality',65)

		#add
		self._pipeline.add(self._queuePhotoElement)
		self._pipeline.add(self._jpegEncElement)

		#link
		self._queuePhotoElement.link(self._jpegEncElement)

	def _tearDownPhotoPipe(self):
		self._pipeline.remove(self._queuePhotoElement)
		self._pipeline.remove(self._jpegEncElement)

		self._queuePhotoElement = None
		self._jpegEncElement = None

	def _attachPhotoPipe(self, doneCallback= None):
		def readyToAttach(success= True):
			if success:
				try:
					photoQueuePad = self._queuePhotoElement.get_static_pad("sink")
					gst.Pad.link(self._teePadPhoto, photoQueuePad)
					self._queuePhotoElement.set_state(gst.State.PLAYING)
					self._jpegEncElement.set_state(gst.State.PLAYING)
					self._photoQueueLinked = True

					if doneCallback:
						doneCallback(True)

					return

				except Exception as e:
					self._logger.error("Error trying to detach video queue: %s", e)

			self.fatalErrorManager()
			if doneCallback:
				doneCallback(False)

		connector = PipelineOperation(self._teePadPhoto, readyToAttach)
		connector.start()

	def _detachPhotoPipe(self, doneCallback= None):
		#Ready callback
		def readyToDetach(success= True):
			if success:
				try:
					self._photoQueueLinked = False
					photoQueuePad = self._queuePhotoElement.get_static_pad("sink")
					gst.Pad.unlink(self._teePadPhoto, photoQueuePad)
					self._queuePhotoElement.set_state(gst.State.NULL)
					self._jpegEncElement.set_state(gst.State.NULL)

					if doneCallback:
						doneCallback(True)

					return

				except Exception as e:
					self._logger.error("Error trying to detach video queue: %s", e)

			self.fatalErrorManager()
			if doneCallback:
				doneCallback(False)

		disconnector = PipelineOperation(self._teePadPhoto, readyToDetach)
		disconnector.start()

	#
	#	 Photo (with text) pipeline setup
	#

	def _setupPhotoTextPipe(self):
		pass

	def _attachPhotoTextPipe(self, doneCallback= None):
		pass

	def _detachPhotoTextPipe(self, doneCallback= None):
		pass

	def tearDown(self):
		self._photoReqs.clear()
		self._photoReqsProcessor.stop()
		self._photoTextReqs.clear()
		self._photoTextReqsProcessor.stop()

		self._pipeline.set_state(gst.State.NULL)
		self._tearDownSourceTee()
		self._tearDownVideoEncodingPipe()

		self._bus.disconnect(self._busOnMessageSignal)
		self._bus.remove_signal_watch()

	def fatalErrorManager(self, message= None):
		self._logger.error('Handling Gstreamer fatal error')

		self._pipeline.set_state(gst.State.PAUSED)
		self._pipeline.set_state(gst.State.NULL)

		self._informClientsOfInterruption(message)

		try:
			self._logger.info("Trying to get list of formats supported by your camera...")
			self._logger.info(subprocess.Popen("v4l2-ctl --list-formats-ext -d /dev/video" + str(self._device), shell=True, stdout=subprocess.PIPE).stdout.read())

		except:
			self._logger.error("Unable to retrieve supported formats")

		if settings().get(["camera", "graphic-debug"]):
			try:
				gst.debug_bin_to_dot_file (self._pipeline, gst.DebugGraphDetails.ALL, "fatal-error")
				self._logger.info("Gstreamer's pipeline dot file created: " + os.getenv("GST_DEBUG_DUMP_DOT_DIR") + "/fatal-error.dot")

			except:
				self._logger.error("Graphic diagram can not created")

		self._manager.resetPipeline()

	def takePhoto(self, doneCallback, text=None):
		if text:
			self._photoTextReqs.appendleft({
				'text': text,
				'callback': doneCallback
			})

			if not self._photoTextReqsProcessor.isAlive():
				self._photoTextReqsProcessor.start()

			if not self._photoTextQueueLinked:
				def onAttachDone(success):
					if success:
						self._photoTextReqsProcessor.setReqsAvailable()

				self._attachPhotoTextPipe(onAttachDone)
			else:
				self._photoTextReqsProcessor.setReqsAvailable()

		else:
			self._photoReqs.appendleft({
				'text': None,
				'callback': doneCallback
			})

			if not self._photoReqsProcessor.isAlive():
				self._photoReqsProcessor.start()

			if not self._photoQueueLinked:
				def onAttachDone(success):
					if success:
						self._photoReqsProcessor.setReqsAvailable()

				self._attachPhotoPipe(onAttachDone)

			else:
				self._photoReqsProcessor.setReqsAvailable()

		self._pipeline.set_state(gst.State.PLAYING)

	def playVideo(self, doneCallback= None):
		if self.state == self.STATE_STREAMING:
			return

		if self.state != self.STATE_PREPARING_STREAMING:
			#Video starter callback
			def videoCanStart():
				try:
					self._attachVideoEncodingPipe()

					stateChanged = self._pipeline.set_state(gst.State.PLAYING)
					if stateChanged == gst.StateChangeReturn.FAILURE:
						return False

					# START PLAYING THE PIPELINE
					self.state = self.STATE_STREAMING
					return True

				except Exception, error:
					self._logger.error("Error starting video stream: %s" % str(error), exc_info = True)
					self._pipeline.set_state(gst.State.PAUSED)
					self._pipeline.set_state(gst.State.NULL)

					return False

			self.state = self.STATE_PREPARING_STREAMING
			if self.state == self.STATE_PHOTO:
				def waitForVideo(timeout):
					startTime = time.time()
					while True:
						if self.state == self.STATE_PHOTO:
							time.sleep(1)
							if (time.time() - startTime) > timeout:
								#Error there as a timeout
								self._logger.error("Timeout (%f secs) starting video stream" % timeout)
								if doneCallback:
									doneCallback(False)

						else:
							result = videoCanStart()
							if doneCallback:
								doneCallback(result)

				starter = Thread(target=waitForVideo, kwargs={'timeout': 20.0})
				starter.start()

			else:
				result = videoCanStart()
				if doneCallback:
					doneCallback(result)

	def stopVideo(self, doneCallback= None):
		# STOPS THE VIDEO
		try:
			"""if self.state == self.STATE_PHOTO:
				self.queuevideo.set_state(gst.State.PAUSED)

			waitingForStopPipeline = True

			self.waitForPlayPipeline = threading.Event()

			while waitingForStopPipeline:
				if self.streamProcessState == 'TAKING_PHOTO' or self.streamProcessState == '':
					waitingForStopPipeline = self.waitForPlayPipeline.wait(2)

				else:
					self.waitForPlayPipeline.set()
					self.waitForPlayPipeline.clear()
					waitingForStopPipeline = False

			self.waitForStopVideo = threading.Event()
			StateChangeReturn = self.stopQueueVideo()
			self.waitForStopVideo.clear()

			self.streamProcessState = 'PAUSED'

			return StateChangeReturn"""

			if self.state == self.STATE_PHOTO:
				self._detachVideoEncodingPipe(doneCallback)
			else:
				self._pipeline.set_state(gst.State.NULL)
				self.state = self.STATE_IDLE
				if doneCallback:
					doneCallback(True)

		except Exception, error:
			self._logger.error("Error stoping video: %s" % str(error), exc_info=True)
			self._pipeline.set_state(gst.State.PAUSED)
			self._pipeline.set_state(gst.State.NULL)

			if doneCallback:
				doneCallback(False)

	### Signal Handlers and Callbacks

	def _onBusMessage(self, bus, msg):
		t = msg.type

		if t == gst.MessageType.ERROR:
			busError, detail = msg.parse_error()

			self._logger.error("gstreamer error: %s\n--- More Info: ---\n%s\n------------------" % (busError, detail))

			if busError.code == 1: #Internal Data Flow Error
				self._informClientsOfInterruption(str(busError))
				self._pipeline.set_state(gst.State.NULL)

		elif t == gst.MessageType.EOS:
			self._logger.info("gstreamer EOS (End of Stream) message received.")

	def _onNoMorePhotoReqs(self):
		def onDetachDone(success):
			#queue detachment is done
			if success:
				self._pipeline.set_state(gst.State.NULL)

		#start photo queue detachemnt
		self._detachPhotoPipe(onDetachDone)

	def _onNoMorePhotoTextReqs(self):
		def onDetachDone(success):
			#queue detachment is done
			if success:
				self._pipeline.set_state(gst.State.NULL)

		#start photo queue detachemnt
		self._detachPhotoTextPipe(onDetachDone)

	### Implement these in child clases

	def _getVideoSourceCaps(self):
		pass

	def _setupVideoEncodingPipe(self):
		pass

	def _tearDownVideoEncodingPipe(self):
		pass


#
#  Worker thread to work on changing pads
#


class PipelineOperation(Thread):
	def __init__(self, pad, readyCallback, timeout=5.0):
		super(PipelineOperation, self).__init__()

		self._readyCallback = readyCallback
		self._pad = pad
		self._waitEvent = Event()
		self._timeout = timeout
		self._callbackCalled = False

	def run(self):
		self._pad.add_probe(gst.PadProbeType.IDLE, self._probeCallback, None)
		self._waitEvent.wait(self._timeout)

		if not self._callbackCalled:
			self._readyCallback(False)

	def _probeCallback(self, pad, info, user_data):
		self._readyCallback(True)
		self._callbackCalled = True
		self._waitEvent.set()
		return gst.PadProbeReturn.REMOVE

#
#  Photo processor. It takes photos from the photo request queue and tries to serve them
#  with the appropiate pipeline. It runs on a separate thread
#

class PhotoReqsProcessor(Thread):
	def __init__(self, photoReqs, element, noMoreReqsCallback ):
		super(PhotoReqsProcessor, self).__init__()

		self._photoReqs = photoReqs
		self._morePhotosEvent = Event()
		self._stopped = False
		self._noMoreReqsCallback = noMoreReqsCallback
		self._element = element

		self._captureEvent = Event()
		self._timeout = 5.0
		self._waitBeforeCapture = 1.5
		self._photoCaptureStart = None
		self._captureProbe = None
		self._callbackCalled = False
		self._readyCallback = None

	def run(self):
		pad = self._element.get_static_pad("src")

		while not self._stopped:
			self._morePhotosEvent.wait()
			self._captureProbe = pad.add_probe(gst.PadProbeType.BUFFER,  self._probeCallback)

			while len(self._photoReqs) > 0:
				if self._stopped:
					return

				req = self._photoReqs.pop()

				self._callbackCalled = False
				self._readyCallback = req['callback']
				self._captureEvent.clear()
				self._photoCaptureStart = time.time()

				self._captureEvent.wait(self._timeout)

				if not self._callbackCalled:
					self._readyCallback(None)

			self._morePhotosEvent.clear()
			self._noMoreReqsCallback()

			pad.remove_probe(self._captureProbe)
			self._captureProbe = None

	def _probeCallback(self, pad, info):
		if not self._callbackCalled and (time.time() - self._photoCaptureStart) > self._waitBeforeCapture:
			photoBuffer = info.get_buffer().map(gst.MapFlags.READ)[1].data
			self._readyCallback(photoBuffer)
			self._callbackCalled = True
			self._captureEvent.set()

		return gst.PadProbeReturn.DROP

	def stop(self):
		self._morePhotosEvent.set()
		self._stopped = True

	def setReqsAvailable(self):
		self._morePhotosEvent.set()

