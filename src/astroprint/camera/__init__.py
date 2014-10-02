# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

# singleton
_instance = None

def cameraManager():
	global _instance
	if _instance is None:
		if platform == "linux" or platform == "linux2":
			from astroprint.cameara.video4linux import CameraV4LManager
			_instance = CameraV4LManager()
		else:
			_instance = CameraManager()

	return _instance

class CameraManager(object):
	def __init__(self):
		print self.list_cameras()

	def list_cameras(self):
		pass
