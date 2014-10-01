# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import cv

# singleton
_instance = None

def cameraManager():
	global _instance
	if _instance is None:
		_instance = CameraManager()

	return _instance

class CameraManager(object):
	def __init__(self):
		pass

	def list_cameras(self):
		pass