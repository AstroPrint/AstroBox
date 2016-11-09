# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import time

from threading import Event

from octoprint.events import eventManager, Events

from astroprint.camera.v4l2 import V4L2Manager
from astroprint.camera.v4l2.gstreamer.pipeline import AstroPrintPipeline
from astroprint.webrtc import webRtcManager

#
#  Camera Manager subclass for GStreamer
#

class GStreamerManager(V4L2Manager):
	name = 'gstreamer'

	def __init__(self):
		self._apPipeline = None
		self.pipeline = None
		self.cameraInfo = None
		self._logger = logging.getLogger(__name__)

		super(GStreamerManager, self).__init__()

	def _doOpenCamera(self):
		if self._apPipeline is None:
			try:
				self._apPipeline = AstroPrintPipeline('/dev/video%d' % self.number_of_video_device, self._settings['size'], self._settings['source'], self._settings['encoding'], self._onApPipelineClosed)
			except Exception as e:
				self._logger.error('Failed to open camera: %s' % e, exc_info= True)
				return False

		return True

	def _onApPipelineClosed(self):
		self.freeMemory()

	def _doCloseCamera(self):
		if self._apPipeline:
			self._apPipeline.stop()
			self._apPipeline = None

	def freeMemory(self):
		self.close_camera()
		webRtcManager().stopJanus()

	def reScan(self):
		try:
			isCameraConnected = self.isCameraConnected()
			tryingTimes = 1

			while not isCameraConnected and tryingTimes < 4:#retrying 3 times for searching camera
				self._logger.info('Camera not found... retrying (%s)' % tryingTimes)
				isCameraConnected = self.isCameraConnected()
				time.sleep(1)
				tryingTimes +=1

			if self._apPipeline:
				self.freeMemory()

			#if at first time Astrobox were turned on without camera, it is
			#necessary to refresh the name
			#print self.cameraInfo
			#if not self.cameraInfo:#starting Astrobox without camera and rescan for adding one of them
			#with this line, if you starts Astrobox without camera, it will try to rescan for camera one time
			#plus, but it is necessary for rescaning a camera after that
			if isCameraConnected:
				self.cameraInfo = { "name": self.getCameraName(), "supportedResolutions": self._getSupportedResolutions() }
				self._logger.info("Found camera %s, encoding: %s and size: %s. Source used: %s" % (self.cameraInfo['name'], self._settings['encoding'] , self._settings['size'], self._settings['source']))

		except Exception, error:
			self._logger.error(error, exc_info=True)
			self._apPipeline = None

		return isCameraConnected

	def _doStartVideoStream(self, doneCallback= None):
		if self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)

		if not self._apPipeline:
			if not self.open_camera():
				if doneCallback:
					doneCallback(False)
				return

		self._apPipeline.startVideo(doneCallback)

	def _doStopVideoStream(self, doneCallback= None):
		if not self._apPipeline or not self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)

		else:
			result = self._apPipeline.stopVideo()

			if doneCallback:
				doneCallback(result)


	def settingsChanged(self, cameraSettings):
		super(GStreamerManager, self).settingsChanged(cameraSettings)

		##When a change in settup is saved, the camera must be shouted down
		##(Janus included, of course)

		eventManager().fire(Events.GSTREAMER_EVENT, {
			'message': 'Your camera settings have been changed. Please reload to restart your video.'
		})
		##

		self.freeMemory()
		self.reScan()

	def _doGetPic(self, done, text=None):
		if self.isCameraConnected():
			if not self._apPipeline:
				if not self.open_camera():
					done(None)
					return

			def onDone(photo):
				done(photo)

			self._apPipeline.takePhoto(onDone, text)
			return

		done(None)

	def shutdown(self):
		self._logger.info('Shutting Down GstreamerManager')
		self.freeMemory()
		webRtcManager().shutdown()

	def isVideoStreaming(self):
		if self._apPipeline:
			waitForDone = Event()
			respCont = [None]

			def onDone(isPlaying):
				if not waitForDone.is_set():
					respCont[0] = isPlaying

			self._apPipeline.isVideoPlaying(onDone)
			waitForDone.wait(1.0)

			return respCont[0]

		else:
			return False

		#return self._apPipeline and self._apPipeline.isVideoPlaying()

	def startLocalVideoSession(self, sessionId):
		return webRtcManager().startLocalSession(sessionId)

	def closeLocalVideoSession(self, sessionId):
		return webRtcManager().closeLocalSession(sessionId)

	@property
	def capabilities(self):
		return ['videoStreaming', 'videoformat-' + self._settings['encoding']]

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
