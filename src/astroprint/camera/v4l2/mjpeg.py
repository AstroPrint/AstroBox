# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import urllib2
import time
import os
import threading
import uuid
import cv2.cv
import numpy as np

from sarge import Command

from octoprint.server import app
from octoprint.settings import settings

from astroprint.camera.v4l2 import V4L2Manager

class MjpegManager(V4L2Manager):
	name = 'mjpeg'

	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._logger.info('MPJEG Camera Manager initialized')
		self._streamer = None
		self._localClients = []

		super(MjpegManager, self).__init__()

	@property
	def _desiredSettings(self):
		return {
			'videoEncoding': [],
			'frameSizes': [
				{'value': '640x480', 'label': 'Low (640 x 480)'},
				{'value': '1280x720', 'label': 'HD 720p (1280 x 720)'},
				{'value': '1920x1080', 'label': 'HD 1080p (1920 x 1080)'}
			],
			'fps': [
				{'value': '5', 'label': '5 fps'}
			],
			'cameraOutput': [
				{'value': 'x-raw', 'label': 'Raw Video'},
				{'value': 'x-mjpeg', 'label': 'MPJEG Encoded'}
			],
			'video_rotation': []
		}

	def settingsChanged(self, cameraSettings):
		super(MjpegManager, self).settingsChanged(cameraSettings)

		if self._streamer:
			self.close_camera()
			self._streamer = None

		self._localClients = []
		self.reScan()

	def _doOpenCamera(self):
		if self.isCameraConnected():
			if self._streamer:
				return True

			else:
				try:
					self._streamer = MJPEGStreamer(self.number_of_video_device, self._settings['size'], self._settings['framerate'], self._settings['format'])

					if self._streamer:
						self.supported_formats = self.cameraInfo['supportedResolutions']
						return True

				except Exception, error:
					self._logger.error(error, exc_info=True)

		return False

	def _doCloseCamera(self):
		if self._streamer:
			if self.isVideoStreaming():
				self.stop_video_stream()

			self._streamer.stop()
			self._streamer = None

		self._localClients = []
		return True

	def _doReScan(self):
		if self._streamer:
			self.close_camera()

		if super(MjpegManager, self)._doReScan():
			self.cameraName = self.getCameraName()
			self.cameraInfo = {"name": self.cameraName, "supportedResolutions": self.supported_formats}

			self._logger.info("Found camera %s, encoding: %s and size: %s. Source used: %s" % (self.cameraName, self._settings['encoding'], self._settings['size'], self._settings['source']))

			return True
		else:
			return False

	def _doStartVideoStream(self, doneCallback= None):
		if self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)

		if not self._streamer:
			if not self.open_camera():
				if doneCallback:
					doneCallback(False)
				return

		result = self._streamer.startVideo()

		if doneCallback:
			doneCallback(result)

	def _doStopVideoStream(self, doneCallback= None):
		if not self._streamer or not self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)

			return

		if self._streamer:
			result = self._streamer.stopVideo()

		if doneCallback:
			doneCallback(result)

	def list_camera_info(self):
		pass

	def list_devices(self):
		pass

	def _doGetPic(self, done, text):
		if self.isCameraConnected():
			if not self._streamer:
				if not self.open_camera():
					done(None)
					return

			threading.Thread(target=self._streamer.getPhoto, args=(done, text)).start()
			return

		done(None)

	def isVideoStreaming(self):
		return self._streamer and self._streamer.isVideoStreaming();

	def isCameraOpened(self):
		return self._streamer is not None

	def startLocalVideoSession(self, sessionId):
		self.open_camera()
		if self._streamer:
			if len(self._localClients) == 0:
				self._streamer.startVideo()

			self._localClients.append(sessionId)
			return True

	def closeLocalVideoSession(self, sessionId):
		if self._streamer:
			try:
				self._localClients.remove(sessionId)

			except ValueError:
				# the sessionId was not active. It's ok we just ignore
				return True

			if len(self._localClients) == 0:
				self._streamer.stopVideo();

			return True


class MJPEGStreamer(object):
	_httpPort = 8085

	def __init__(self, videoDevice, size, fps, format):
		self._logger = logging.getLogger(__name__)
		self._device = '/dev/video%d' % videoDevice
		self._size = size
		self._fps = fps
		self._format = format
		self._videoRunning = False
		self._process = None
		self._streaming = False
		self._needsExposure = True

		self._infoArea = cv2.imread(os.path.join(app.static_folder, 'img', 'camera-info-overlay.jpg'), cv2.cv.CV_LOAD_IMAGE_COLOR)
		self._infoAreaShape = self._infoArea.shape

		#precalculated stuff
		watermark = cv2.imread(os.path.join(app.static_folder, 'img', 'astroprint_logo.png'))
		watermark = cv2.resize( watermark, ( 100, 100 * watermark.shape[0]/watermark.shape[1] ) )

		self._watermarkShape = watermark.shape

		watermarkMask = cv2.cvtColor(watermark, cv2.COLOR_BGR2GRAY) / 255.0
		watermarkMask = np.repeat( watermarkMask, 3).reshape( (self._watermarkShape[0],self._watermarkShape[1],3) )
		self._watermakMaskWeighted = watermarkMask * watermark
		self._watermarkInverted = 1.0 - watermarkMask

	def startStreamer(self):
		if not self._process:
			command = [
				"/mjpeg_streamer/mjpg_streamer",
				"-i",
				"input_uvc.so -d %s -f %s -r %s --no_dynctrl%s" % (self._device, self._fps, self._size, ' -y' if self._format == 'x-raw' else ''),
				"-o",
				"output_http.so -p %d" % self._httpPort
			]

			self._process = Command(command, env={'LD_LIBRARY_PATH': '/mjpeg_streamer'}, stderr=open(os.devnull, 'w'))
			if self._process:
				self._process.run(async=True)

				time.sleep(0.2)

				running = self._process.returncode is None

				return running

		return False

	def startVideo(self):
		if self._streaming:
			return True

		if self.startStreamer():
			self._streaming = True
			return True

		return False

	def stop(self):
		if self._process:
			if self._process.returncode is None:
				self._process.terminate()
				tries = 4
				while self._process.returncode is None:
					if tries > 0:
						tries -= 1
						time.sleep(0.5)
						self._process.poll()
					else:
						break

				if self._process.returncode is None:
					self._logger.warn('Unable to terminate nicely, killing the process.')
					self._process.kill()
					self._process.wait()

			self._process = None

		self._streaming = False
		self._needsExposure = True

	def stopVideo(self):
		self._streaming = False

	def isVideoStreaming(self):
		return self._streaming

	def getPhoto(self, doneCb, text=None):
		image = None

		if not self._process:
			if not self.startStreamer():
				self._logger.error('Unable to start MJPEG Streamer')
				doneCb(None)
				return

		try:
			if self._needsExposure and not self.isVideoStreaming():
				time.sleep(1.8) # we need to give the camera some time to stabilize the image. 1.8 secs has been tested to work in low end cameras
				self._needsExposure = False

			response = urllib2.urlopen('http://127.0.0.1:%d?action=snapshot' % self._httpPort)
			image = response.read()

		except urllib2.URLError as e:
			self._logger.error(e)

		if image and text:
			decodedImage = cv2.imdecode(np.fromstring(image, np.uint8), cv2.CV_LOAD_IMAGE_COLOR)
			self._apply_watermark(decodedImage, text)
			image = cv2.cv.EncodeImage('.jpeg', cv2.cv.fromarray(decodedImage), [cv2.cv.CV_IMWRITE_JPEG_QUALITY, 80]).tostring()

		doneCb(image)

	def _apply_watermark(self, img, text):
		if text and img != None:
			imgPortion = img[-(self._watermarkShape[0]+5):-5, -(self._watermarkShape[1]+5):-5]
			img[-(self._watermarkShape[0]+5):-5, -(self._watermarkShape[1]+5):-5] = (self._watermarkInverted * imgPortion) + self._watermakMaskWeighted

			img[:self._infoAreaShape[0], :self._infoAreaShape[1]] = self._infoArea
			cv2.putText(img, text, (30,17), cv2.FONT_HERSHEY_PLAIN, 1.0, (81,82,241), thickness=1)

			return True

		return False

