# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import cv2

from os import listdir

from astroprint.camera import CameraManager

class CameraV4LManager(CameraManager):
	def list_cameras(self):
		return listdir('/sys/class/video4linux')

	def save_pic(self):
		camera = cv2.VideoCapture(0)
		for i in range(30):
			camera.read()

		s, img = camera.read()
		if s:
			cv2.imwrite('/sdcard/development/AstroBox/src/astroprint/static/img/text.jpeg', img)
		else:
			print "Error getting image"

		del(camera)

