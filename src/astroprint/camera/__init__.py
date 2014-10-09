# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from sys import platform

# singleton
_instance = None

def cameraManager():
	global _instance
	if _instance is None:
		if platform == "linux" or platform == "linux2":
			from astroprint.camera.video4linux import CameraV4LManager
			_instance = CameraV4LManager()
		elif platform == "darwin":
			from astroprint.camera.mac import CameraMacManager
			_instance = CameraMacManager()

	return _instance

class CameraManager(object):
	def __init__(self):
		pass

	def open_camera(self):
		return False

	def close_camera(self):
		pass

	def list_camera_info(self):
		pass

	def list_devices(self):
		pass

	def get_pic(self, text=None):
		pass
		
	def save_pic(self, filename, text=None):
		pass

	def isCameraAvailable(self):
		return False
