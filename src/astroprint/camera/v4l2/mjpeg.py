# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import urllib2
import time
import os
import threading

from sarge import Command

from astroprint.camera.v4l2 import V4L2Manager

from octoprint.settings import settings

class MjpegManager(V4L2Manager):
	def __init__(self, videoDevice):
		self._logger = logging.getLogger(__name__)
		self._logger.info('MPJEG Camera Manager initialized')
		self._videoDevice = videoDevice
		self._settings = None
		self._isStreaming = False

		s = settings()

		self._settings = {
			'size': s.get(["camera", "size"]),
			'framerate': s.get(["camera", "framerate"]),
			'format': s.get(["camera", "format"])
		}

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
		self.stop_video_stream()
		self._settings = cameraSettings
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


class MJPEGStreamer(object):
	_httpPort = 8085

	def __init__(self, videoDevice, size, fps, format):
		self._device = '/dev/video%d' % videoDevice
		self._size = size
		self._fps = fps
		self._format = format
		self._videoRunning = False
		self._process = None

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
			response = urllib2.urlopen('http://localhost:%d?action=snapshot' % self._httpPort)
			image = response.read()

		except urllib2.URLError:
			pass

		if stopAfterPhoto:
			self.stopVideo()

		if doneCb:
			doneCb(image)

		else:
			return image
			
