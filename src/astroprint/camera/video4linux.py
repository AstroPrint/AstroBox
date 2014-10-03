# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import cv2.cv
import logging
import numpy

from os import listdir

from astroprint.camera import CameraManager

class CameraV4LManager(CameraManager):
	def __init__(self,):
		self._camera = None
		self._feed = None
		self._logger = logging.getLogger(__name__)

	def list_cameras(self):
		cameras = listdir('/sys/class/video4linux')
		result = []
		for c in cameras:
			with open('/sys/class/video4linux/%s/name' % c, 'r') as name_file:
				result.append({
					'id': c,
					'name': name_file.read().replace('\n', '')
				})

		return result

	def get_pic(self):
		img = self._snapshot_from_camera()

		if img != None:
			cv2.rectangle(img, (0,0), (200, 20), (0,0,0), cv2.cv.CV_FILLED)
			cv2.putText(img, "60% - Layer 1/23", (10,15), cv2.FONT_HERSHEY_PLAIN, 1.0, (255,255,255))
			return cv2.cv.EncodeImage('.jpeg', cv2.cv.fromarray(img), [cv2.cv.CV_IMWRITE_JPEG_QUALITY, 50])

	def save_pic(self, filename):
		img = self._snapshot_from_camera()
		if img != None:
			return cv2.imwrite(filename, img)

	def _snapshot_from_camera(self):
		if not self._camera:
			self._open_camera()

		#discard some frames buffered by the camera
		for i in range(5):
			self._camera.grab()

		retval, img = self._camera.retrieve()
		if retval:
			return img

		self._logger.error('Not able to read image from camera')
		return None

	def _close_camera(self):
		self._camera.release()
		del(self._camera)
		self._camera = None
		self._feed.join()
		self._feed = None

	def _open_camera(self):
		self._camera = cv2.VideoCapture()
		self._camera.open(0)
