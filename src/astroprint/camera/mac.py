# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os.path
import glob

from random import randrange
from astroprint.camera import CameraManager

class CameraMacManager(CameraManager):
	def __init__(self):
		super(CameraMacManager, self).__init__()

		self._files = [f for f in glob.glob(os.path.join(os.path.realpath(os.path.dirname(__file__)+'/../../../local'),"camera_test*.jpeg"))]

	def open_camera(self):
		return True

	def get_pic(self, text=None):
		fileCount = len(self._files)

		if fileCount:
			imageFile = self._files[randrange(fileCount)]
			with open(imageFile, "r") as f:
				image = f.read()

			return image

		else:
			return None

	def isCameraAvailable(self):
		return True
