# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import subprocess

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

		#probe holders
		self._teePadVideoEncProbe = None

		#Events for synchronization
		self._waitForPhoto = None
		self._waitForPlayVideo = None

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
		self._videoLogoElement.unlink(self._teeElement)
		self._videoSourceCaps.unlink(self._videoLogoElement)
		self._videoSourceElement.unlink(self._videoSourceCaps)

		#remove elements
		self._pipeline.remove(self._videoSourceElement)
		self._pipeline.remove(self._videoLogoElement)
		self._pipeline.remove(self._videoSourceCaps)
		self._pipeline.remove(self._teeElement)

	def _attachVideoEncodingPipe(self):
		videoQueuePad = self._queueVideoElement.get_static_pad("sink")
		gst.Pad.link(self._teePadVideoEnc, videoQueuePad)
		self._queueVideoElement.set_state(gst.State.PLAYING)

	def _detachVideoEncodingPipe(self):

		#Ready callback
		def readyToDetach(success= True):
			if success:
				try:
					videoQueuePad = self._queueVideoElement.get_static_pad("sink")
					gst.Pad.unlink(self._teePadVideoEnc, videoQueuePad)
					return

				except:
					pass

			self._logger.error("Error trying to detach video queue: %s", error)
			self.fatalErrorManager(None, True, True)

		disconnector = PipelineDisconnector(self._teePadVideoEnc, readyToDetach)
		disconnector.start()

		#try:
		#	self._teePadVideoEnc.add_probe(gst.PadProbeType.BLOCK, self._teePadVideoEncProbeCallback, None)
		#	self._waitForStopVideo.wait()

		#except Exception, error:
		#	self._logger.error("Error trying to stop video queue: %s", error)
		#	self.fatalErrorManager(None, True, True)

	#def _teePadVideoEncProbeCallback(self, pad, info, user_data):
	#	self._teePadVideoEnc.add_probe(gst.PadProbeType.BLOCK_DOWNSTREAM, self._teePadVideoEncProbeDownstreamCallback, None)
	#	return gst.PadProbeReturn.REMOVE

	#def _teePadVideoEncProbeDownstreamCallback(self, pad, info, user_data):
	#	videoQueuePad = self._queueVideoElement.get_static_pad("sink")
	#	gst.Pad.unlink(self._teePadVideoEnc, videoQueuePad)
	#	self._waitForStopVideo.set()

	#	return gst.PadProbeReturn.REMOVE

	def tearDown(self):
		self._pipeline.set_state(gst.State.NULL)
		self._tearDownSourceTee()
		self._tearDownVideoEncodingPipe()

		self._bus.disconnect(self._busOnMessageSignal)
		self._bus.remove_signal_watch()

	def fatalErrorManager(self, Message=None, SendToLocal=True, SendToRemote=True):
		self._logger.error('Handling Gstreamer fatal error')

		self._pipeline.set_state(gst.State.PAUSED)
		self._pipeline.set_state(gst.State.NULL)

		#TODO: if Photo pending stop waiting
		#if self.waitForPhoto:
		#	self.stopQueuePhotoNotText()
		#	self.waitForPhoto.set()

		if SendToRemote:
			#signaling for remote peers
			manage_fatal_error_webrtc = signal('manage_fatal_error_webrtc')
			manage_fatal_error_webrtc.send('cameraError',message=Message)

		if SendToLocal:
			#event for local peers
			eventManager().fire(Events.GSTREAMER_EVENT, {
				'message': Message or 'Fatal error occurred in video streaming'
			})

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

	def takePhoto(self):
		pass

	def playVideo(self):
		if self.state == self.STATE_STREAMING:
			return

		if self.state != self.STATE_PREPARING_STREAMING:
			# SETS VIDEO ENCODING PARAMETERS AND STARTS VIDEO
			try:
				waitingForVideo = True

				self._waitForPlayVideo = Event()

				if self.state == self.STATE_PHOTO:
					while waitingForVideo:
						if self.state == self.STATE_PHOTO:
							waitingForVideo = self._waitForPlayVideo.wait(2)
						else:
							self._waitForPlayVideo.set()
							self._waitForPlayVideo.clear()
							waitingForVideo = False

				self.state = self.STATE_PREPARING_STREAMING
				print "attaching"
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

	def stopVideo(self):
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
				self._detachVideoEncodingPipe()
			else:
				self._pipeline.set_state(gst.State.NULL)
				self.state == self.STATE_IDLE

			return True

		except Exception, error:
			self._logger.error("Error stoping video: %s" % str(error), exc_info=True)
			self._pipeline.set_state(gst.State.PAUSED)
			self._pipeline.set_state(gst.State.NULL)

			return False


	### Signal Handlers and Callbacks

	def _onBusMessage(self, bus, msg):
		t = msg.type

		if t == gst.MessageType.ERROR:
			busError, detail = msg.parse_error()

			self._logger.error("gstreamer bus message error: %s" % busError)

			#if self.waitForPhoto:
			#	if self.photoMode == 'NOT_TEXT':
			#		self.stopQueuePhotoNotText()
			#	else:
			#		self.stopQueuePhoto()
			#
			#	self.waitForPhoto.set()

			if 'Internal data flow error.' in str(busError):
				message = str(busError)
				self.fatalErrorManager(message, True, True)

		elif t == gst.MessageType.EOS:
			self._logger.info("gstreamer EOS (End of Stream) message received.")

	### Implement these in child clases

	def _getVideoSourceCaps(self):
		pass

	def _setupVideoEncodingPipe(self):
		pass

	def _tearDownVideoEncodingPipe(self):
		pass


#
#  Worker thread to disconnect pipelines
#

class PipelineDisconnector(Thread):
	def __init__(self, pad, readyCallback, timeout=20.0):
		super(PipelineDisconnector, self).__init__()

		self._readyCallback = readyCallback
		self._pad = pad
		self._waitEvent = Event()
		self._timeout = timeout

	def run(self):
		self._pad.add_probe(gst.PadProbeType.IDLE, self._probeCallback, None)
		waitResult = self._waitEvent.wait(self._timeout)

		self._readyCallback(waitResult)

	def probeCallback(self):
		self._waitEvent.set()
		return gst.PadProbeReturn.REMOVE


