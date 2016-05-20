# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from astroprint.camera.v4l2 import V4L2Manager

class MjpegManager(V4L2Manager):
	def __init__(self, videoDevice):
		self._logger = logging.getLogger(__name__)
		self._logger.info('MPJEG Camera Manager initialized')
		self._videoDevice = videoDevice
		self._settings = None

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

	def open_camera(self):
		try:
			if self.isCameraConnected():
				self._streamer = MJPEGStreamer(self._videoDevice)

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
			self._streamer.startVideo()
			return True
		else:
			return False

	def stop_video_stream(self):
		if self._streamer:
			self._streamer.stopVideo()
			return True
		else:
			return False

	def list_camera_info(self):
		pass

	def list_devices(self):
		pass

	def get_pic(self, text=None):
		pass

	def get_pic_async(self, done, text=None):
		pass

	def save_pic(self, filename, text=None):
		pass



class MJPEGStreamer(object):
	_httpPort = 8085

	def __init__(self, videoDevice):
		self._device = '/dev/video%d' % videoDevice
		self._videoRunning = False
		self._process = None

	def startVideo(self, resolution, fps, deviceInput):
		if not self._process:
			command = "/mjpeg_streamer/mjpg_streamer -i '/mjpeg_streamer/input_uvc.so -d %d -f %d -r %s --no_dynctrl%s' -o '/mjpeg_streamer/output_http.so -p %d" % \
			(	
				self._device,
				fps,
				resolution,
				' -y' if deviceInput == 'x-raw' else '',
				self._httpPort
			)

			print command

	def stopVideo(self):
		self._process = None

	def getSnapshot(self):
		pass
