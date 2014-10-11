# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os.path

from astroprint.camera import CameraManager

class CameraMacManager(CameraManager):
	def open_camera(self):
		return True

	def get_pic(self, text=None):
		imageFile = os.path.join(os.path.realpath(os.path.dirname(__file__)+'/../../../local'), "camera_test.jpeg")
		if os.path.isfile(imageFile):
			with open(imageFile, "r") as f:
				image = f.read()

			return image

		else:
			return None

	def isCameraAvailable(self):
		return True
