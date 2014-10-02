# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from os import listdir

from astroprint.camera import CameraManager

class CameraV4LManager(CameraManager):
	def list_cameras(self):
		return listdir('/sys/class/video4linux')