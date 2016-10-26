# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import subprocess
import logging
import time
import gi

from threading import Thread, Semaphore

from octoprint.settings import settings

from astroprint.camera.v4l2 import V4L2Manager
from astroprint.camera.v4l2.gstreamer.pipelines import pipelineFactory
from astroprint.webrtc import webRtcManager

#
#  GStreamer Initialization
#

gstreamer_debug_level = settings().get(["camera", "debug-level"])

if settings().get(["camera", "graphic-debug"]):
	os.environ['GST_DEBUG'] = '*:' + str(gstreamer_debug_level)
	#os.environ['GST_DEBUG_NO_COLOR'] = '1'
	os.environ['GST_DEBUG_DUMP_DOT_DIR'] =  '/home/pi'
	os.environ['GST_DEBUG_DUMP_DIR_DIR'] =  '/home/pi'

try:
	gi.require_version('Gst', '1.0')
except ValueError:
	raise ImportError

from gi.repository import Gst as gst

if gstreamer_debug_level > 0:
	gst.debug_set_active(True)
	gst.debug_set_default_threshold(gstreamer_debug_level)

gst.init(None)

#
#  Camera Manager subclass for GStreamer
#

class GStreamerManager(V4L2Manager):
	name = 'gstreamer'

	def __init__(self, videoDevice):
		self.gstreamerVideo = None
		self.asyncPhotoTaker = None
		self.pipeline = None
		self.cameraInfo = None
		self.number_of_video_device = videoDevice
		self._logger = logging.getLogger(__name__)

		if super(GStreamerManager, self).isCameraConnected():
			self.reScan()

		super(GStreamerManager, self).__init__(videoDevice)

	def isCameraConnected(self):
		return super(GStreamerManager, self).isCameraConnected() and self.gstreamerVideo is not None

	def open_camera(self):
		if self.gstreamerVideo is None:
			return self.reScan(self.cameraInfo)

		return True

	def freeMemory(self):
		self.stop_video_stream()
		webRtcManager().stopJanus()

		if self.gstreamerVideo:
			self.gstreamerVideo.tearDown()
			self.gstreamerVideo = None

	def reScan(self, cameraInfo=None):
		try:
			isCameraConnected = super(GStreamerManager, self).isCameraConnected()
			tryingTimes = 1

			while not isCameraConnected and tryingTimes < 4:#retrying 3 times for searching camera
				self._logger.info('Camera not found... retrying (%s)' % tryingTimes)
				isCameraConnected = super(GStreamerManager, self).isCameraConnected()
				time.sleep(1)
				tryingTimes +=1

			if self.gstreamerVideo:
				self.freeMemory()
				self.gstreamerVideo = None
				self.cameraInfo = None

			#if at first time Astrobox were turned on without camera, it is
			#necessary to refresh the name
			#print self.cameraInfo
			#if not self.cameraInfo:#starting Astrobox without camera and rescan for adding one of them
			#with this line, if you starts Astrobox without camera, it will try to rescan for camera one time
			#plus, but it is necessary for rescaning a camera after that
			if isCameraConnected:
				#self.pipeline = GstPipeline()
				#self.initGstreamerBus()

				self.cameraInfo = { "name": self.getCameraName(), "supportedResolutions": self._getSupportedResolutions() }

				s = settings()
				encoding = s.get(["camera", "encoding"])
				source = s.get(["camera", "source"])

				self._logger.info("Initializing Gstreamer with camera %s, encoding: %s and size: %s. Source used: %s" % (self.cameraInfo['name'], encoding , s.get(["camera", "size"]), source))
				self.gstreamerVideo = pipelineFactory( self, self.number_of_video_device, s.get(["camera", "size"]), source, encoding  )

		except Exception, error:
			self._logger.error(error, exc_info=True)
			self.gstreamerVideo = None

		return not self.gstreamerVideo is None

	def start_video_stream(self):
		if self.gstreamerVideo:
			if not self.isVideoStreaming():
				return self.gstreamerVideo.playVideo()
			else:
				return True

		else:
			return False

	def stop_video_stream(self):
		if self.gstreamerVideo and self.gstreamerVideo.state == self.gstreamerVideo.STATE_STREAMING:
			return self.gstreamerVideo.stopVideo()

		else:
			return False

	def settingsChanged(self, cameraSettings):
		super(GStreamerManager, self).settingsChanged(cameraSettings)

		##When a change in settup is saved, the camera must be shouted down
		##(Janus included, of course)

		eventManager().fire(Events.GSTREAMER_EVENT, {
			'message': 'Your camera settings have been changed. Please reload to restart your video.'
		})
		##

		#initialize a new object with the settings changed
		if self.asyncPhotoTaker:
			self.asyncPhotoTaker.stop()
			self.asyncPhotoTaker = None

		self.freeMemory()
		self.open_camera()

	# def list_camera_info(self):
	#    pass

	# def list_devices(self):
	#    pass

	# There are cases where we want the pic to be synchronous
	# so we leave this version too
	def get_pic(self, text=None):
		if self.gstreamerVideo:
			return self.gstreamerVideo.takePhoto(text)

		return None

	def get_pic_async(self, done, text=None):
		# This is just a placeholder
		# we need to pass done around and call it with
		# the image info when ready
		if not self.gstreamerVideo:
			done(None)
			return

		if not self.asyncPhotoTaker:
			self.asyncPhotoTaker = AsyncPhotoTaker(self.gstreamerVideo.takePhoto)

		self.asyncPhotoTaker.take_photo(done, text)

	# def save_pic(self, filename, text=None):
	#    pass

	def shutdown(self):
		self._logger.info('Shutting Down GstreamerManager')
		self.freeMemory()
		gst.deinit()
		webRtcManager().shutdown()

	def isVideoStreaming(self):
		return self.gstreamerVideo.state == self.gstreamerVideo.STATE_STREAMING

	def getVideoStreamingState(self):
		return self.gstreamerVideo.streamProcessState

	def close_camera(self):
			if self.asyncPhotoTaker:
				self.asyncPhotoTaker.stop()
				self.asyncPhotoTaker.join()
				self.asyncPhotoTaker = None

	def startLocalVideoSession(self, sessionId):
		return webRtcManager().startLocalSession(sessionId)

	def closeLocalVideoSession(self, sessionId):
		return webRtcManager().closeLocalSession(sessionId)

	@property
	def capabilities(self):
		return ['videoStreaming', 'videoformat-' + self._settings['encoding']]

	## From V4L2Manager
	def _broadcastFataError(self, msg):
		self.gstreamerVideo.fatalErrorManage(True, True, msg, False, True)

	@property
	def _desiredSettings(self):
		return {
			'busSource': [
				{'value': 'USB', 'label': 'USB Camera'},
				{'value': 'raspicam', 'label': 'Raspicam'}
			],
			'frameSizes': [
				{'value': '640x480', 'label': 'Low (640 x 480)'},
				{'value': '1280x720', 'label': 'High (1280 x 720)'}
			],
			'cameraOutput': [
				{'value': 'x-raw', 'label': 'Raw Video'}
			],
			'fps': [],
			'videoEncoding': [
				{'value': 'h264', 'label': 'H.264'},
				{'value': 'vp8', 'label': 'VP8'}
			]
		}

	#Virtual Interface GStreamerEvents

	def resetPipeline(self):
		self.freeMemory()
		if super(GStreamerManager, self).isCameraConnected():
			self.setSafeSettings()
			self.reScan()


#
#  Class to allow for taking pictures asynchronously
#


class AsyncPhotoTaker(Thread):
	def __init__(self, take_photo_function):
		super(AsyncPhotoTaker, self).__init__()

		self.threadAlive = True
		self.take_photo_function = take_photo_function
		self.sem = Semaphore(0)
		self.doneFunc = None
		self.text = None
		self.start()

	def run(self):
		while self.threadAlive:
			self.sem.acquire()
			if not self.threadAlive:
				return

			if self.doneFunc:
				self.doneFunc(self.take_photo_function(self.text))
				self.doneFunc = None
				self.text = None

	def take_photo(self, done, text):
		self.doneFunc = done
		self.text = text
		self.sem.release()

	def stop(self):
		self.threadAlive = False
		self.sem.release()

