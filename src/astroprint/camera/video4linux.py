# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import cv2.cv
import logging
import numpy as np
import os

from octoprint.server import app

from astroprint.camera import CameraManager

class CameraV4LManager(CameraManager):
	def __init__(self,):
		self._camera = None
		self._feed = None
		self._logo = None
		self._logger = logging.getLogger(__name__)


	def list_cameras(self):
		cameras = os.listdir('/sys/class/video4linux')
		result = []
		for c in cameras:
			with open('/sys/class/video4linux/%s/name' % c, 'r') as name_file:
				result.append({
					'id': c,
					'name': name_file.read().replace('\n', '')
				})

		return result

	def get_pic(self, text=None):
		img = self._snapshot_from_camera()

		if img != None:
			if text:
				self._apply_watermark(img, text)

			return cv2.cv.EncodeImage('.jpeg', cv2.cv.fromarray(img), [cv2.cv.CV_IMWRITE_JPEG_QUALITY, 75])

	def save_pic(self, filename, text=None):
		img = self._snapshot_from_camera()
		if img != None:
			if text:
				self._apply_watermark(img, text)

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

	def _apply_watermark(self, img, text):
		if text and img != None:
			cv2.rectangle(img, (0,0), (200, 25), (255,255,255), cv2.cv.CV_FILLED)
			cv2.putText(img, text, (30,17), cv2.FONT_HERSHEY_PLAIN, 1.0, (81,82,241), thickness=1)

			imgPortion = img[2:self._logoShape[0]+2, 2:self._logoShape[1]+2]
			overlay = np.zeros_like(imgPortion, "uint16")
			overlay = self._logo

			img[2:self._logoShape[0]+2, 2:self._logoShape[1]+2] = np.array(np.clip(imgPortion + overlay, 0, 255), "uint8")

			return True

		return False

	def _close_camera(self):
		self._camera.release()
		del(self._camera)
		del(self._logo)
		self._camera = None
		self._feed.join()
		self._feed = None
		self._logo = None

	def _open_camera(self):
		self._camera = cv2.VideoCapture()
		self._camera.open(0)
		logo = cv2.imread(os.path.join(app.static_folder, 'favicon.ico'), cv2.cv.CV_LOAD_IMAGE_COLOR)
		self._logo = cv2.resize(logo, (20,20))
		self._logoShape = self._logo.shape
