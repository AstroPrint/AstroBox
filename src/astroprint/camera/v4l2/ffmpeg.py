# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from astroprint.camera.v4l2 import V4L2Manager

class FfmpegManager(V4L2Manager):
	def __init__(self, videoDevice):
		self._logger = logging.getLogger(__name__)
		self._logger.info('FFMPEG Camera Manager initialized')

		super(FfmpegManager, self).__init__(videoDevice)

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
		pass

	def open_camera(self):
		try:
			if self.isCameraConnected():
				self.supported_formats = self._getSupportedResolutions()

			return True

		except Exception, error:
			self._logger.error(error, exc_info=True)

		return False

	def close_camera(self):
		pass

	def start_video_stream(self):
		pass

	def stop_video_stream(self):
		pass

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
