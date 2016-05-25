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

from astroprint.camera.v4l2 import V4L2Manager

class MjpegManager(V4L2Manager):
	def __init__(self, videoDevice):
		self._logger = logging.getLogger(__name__)
		self._logger.info('MPJEG Camera Manager initialized')
		self._videoDevice = videoDevice
		self._isStreaming = False
		self._localClients = []

		super(MjpegManager, self).__init__(videoDevice)

	def settingsStructure(self):
		return {
			'videoEncoding': [],
			'frameSizes': [
				{'value': '640x480', 'label': 'Low (640 x 480)'},
				{'value': '1280x720', 'label': 'High (1280 x 720)'}
			],
			'fps': [
				{'value': '5', 'label': '5 fps'}
			],
			'cameraOutput': [
				{'value': 'x-raw', 'label': 'Raw Video'},
				{'value': 'x-mjpeg', 'label': 'MPJEG Encoded'}
			]
		}

	def settingsChanged(self, cameraSettings):
		super(MjpegManager, self).settingsChanged(cameraSettings)

		self.stop_video_stream()
		self._localClients = []
		self._streamer = None
		self.open_camera()

	def open_camera(self):
		try:
			if self.isCameraConnected():
				self._streamer = MJPEGStreamer(self._videoDevice, self._settings['size'], self._settings['framerate'], self._settings['format'])

				if self._streamer:
					self.supported_formats = self._getSupportedResolutions()

			return True

		except Exception, error:
			self._logger.error(error, exc_info=True)

		return False

	def close_camera(self):
		self.stop_video_stream()
		self._localClients = []
		self._streamer = None

	def start_video_stream(self):
		if self._streamer:
			if not self._isStreaming:
				self._streamer.startVideo()
				self._isStreaming = True
			return True
		else:
			return False

	def stop_video_stream(self):
		if self._streamer:
			self._streamer.stopVideo()
			self._isStreaming = False
			return True
		else:
			return False

	def list_camera_info(self):
		pass

	def list_devices(self):
		pass

	def get_pic(self, text=None):
		if self._streamer:
			return self._streamer.getPhoto(text)

		else:
			return None

	def get_pic_async(self, done, text=None):
		if self._streamer:
			threading.Thread(target=self._streamer.getPhoto, args=(text, done)).start()

		else:
			done(None)

	def isVideoStreaming(self):
		return self._isStreaming;

	def startLocalVideoSession(self, sessionId):
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
		self._device = '/dev/video%d' % videoDevice
		self._size = size
		self._fps = fps
		self._format = format
		self._videoRunning = False
		self._process = None


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

	def startVideo(self):
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

				return self._process.returncode is None

		return False

	def stopVideo(self):
		if self._process:
			if self._process.returncode is None:
				self._process.terminate()
				self._process.wait()
			
			self._process = None

	def getPhoto(self, text=None, doneCb=None):
		image = None
		stopAfterPhoto = False

		if not self._process:
			self.startVideo()
			stopAfterPhoto = True

		try:
			time.sleep(0.5) # we need to give the camera some time to stabilize the image
			response = urllib2.urlopen('http://127.0.0.1:%d?action=snapshot' % self._httpPort)
			image = response.read()

		except urllib2.URLError:
			pass

		if image and text:
			decodedImage = cv2.imdecode(np.fromstring(image, np.uint8), cv2.CV_LOAD_IMAGE_COLOR)
			self._apply_watermark(decodedImage, text)
			image = cv2.cv.EncodeImage('.jpeg', cv2.cv.fromarray(decodedImage), [cv2.cv.CV_IMWRITE_JPEG_QUALITY, 80]).tostring()

		if stopAfterPhoto:
			self.stopVideo()

		if doneCb:
			doneCb(image)

		else:
			return image

	def _apply_watermark(self, img, text):
			if text and img != None:
				imgPortion = img[-(self._watermarkShape[0]+5):-5, -(self._watermarkShape[1]+5):-5]
				img[-(self._watermarkShape[0]+5):-5, -(self._watermarkShape[1]+5):-5] = (self._watermarkInverted * imgPortion) + self._watermakMaskWeighted

				img[:self._infoAreaShape[0], :self._infoAreaShape[1]] = self._infoArea
				cv2.putText(img, text, (30,17), cv2.FONT_HERSHEY_PLAIN, 1.0, (81,82,241), thickness=1)

				return True

			return False
			
