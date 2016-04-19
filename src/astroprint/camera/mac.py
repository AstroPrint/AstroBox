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
	def __init__(self):
		super(CameraMacManager, self).__init__()

		self._logger = logging.getLogger(__name__)
		self._files = [f for f in glob.glob(os.path.join(os.path.realpath(os.path.dirname(__file__)+'/../../../local'),"camera_test*.jpeg"))]

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

	def isCameraAvailable(self):
		return True

	def _doGetPicAsync(self, done, text):
		done(self.get_pic(text))
