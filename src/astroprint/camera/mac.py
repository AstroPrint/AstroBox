# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os.path
import glob
import logging
import threading

from random import randrange
from astroprint.camera import CameraManager

class CameraMacManager(CameraManager):
	name = 'mac'

	def __init__(self):
		super(CameraMacManager, self).__init__()

		self._logger = logging.getLogger(__name__)
		self._files = [f for f in glob.glob(os.path.join(os.path.realpath(os.path.dirname(__file__)+'/../../../local'),"camera_test*.jpeg"))]
		self.cameraName = 'Test Camera'
		self._logger.info('Mac Simulation Camera Manager initialized')

	def settingsStructure(self):
		return {
			'videoEncoding': [],
			'frameSizes': [
				{'value': '640x480', 'label': 'Low (640 x 480)'},
				{'value': '1280x720', 'label': 'High (1280 x 720)'}
			],
			'fps': [
				{'value': '5', 'label': '5 fps'},
				{'value': '10', 'label': '10 fps'}
			],
			'cameraOutput': [
				{'value': 'files', 'label': 'Files'}
			]
		}

	def open_camera(self):
		return True

	def get_pic_async(self, done, text=None):
		threading.Timer(3, self._doGetPicAsync,[done, text]).start()

	def get_pic(self, text=None):
		fileCount = len(self._files)
		image = None

		if fileCount:
			imageFile = self._files[randrange(fileCount)]
			with open(imageFile, "r") as f:
				image = f.read()

		return image

	@property
	def capabilities(self):
		#return ['videoStreaming']
		return []

	def isCameraConnected(self):
		return True

	def hasCameraProperties(self):
		return True

	def isResolutionSupported(self, resolution):
		return resolution == '640x480'

	def _doGetPicAsync(self, done, text):
		done(self.get_pic(text))
