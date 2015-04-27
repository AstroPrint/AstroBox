# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import cv2.cv
import logging
import numpy as np
import os

from octoprint.server import app

from astroprint.camera import CameraManager

class CameraV4LManager(CameraManager):
	def __init__(self):
		self._camera = None
		self._watermakMaskWeighted = None
		self._watermarkInverted = None
		self._infoArea = None		
		self._logger = logging.getLogger(__name__)
		self._camerasDir = '/sys/class/video4linux'

		super(CameraV4LManager, self).__init__()


	def open_camera(self):
		if self.isCameraAvailable():
			return True

		cameras = self.list_devices()

		if cameras:	
			try:		
				self._camera = cv2.VideoCapture()

			except Exception as e:
				self._logger.error('Error creating VideoCapture object: %s' % e)
				self._camera = None
				return False

			if not self._camera:
				return False

			if self._camera.open(int(cameras[0].replace('video',''))):
				try:
					self._camera.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 640)
					self._camera.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
				except Exception as e:
					self._logger.error('Error setting camera frame to 800x448 size: %s' % e)

				self._infoArea = cv2.imread(os.path.join(app.static_folder, 'img', 'camera-info-overlay.jpg'), cv2.cv.CV_LOAD_IMAGE_COLOR)
				self._infoAreaShape = self._infoArea.shape

				#precalculated stuff
				watermark = cv2.imread(os.path.join(app.static_folder, 'img', 'astroprint_logo.png'))
				watermark = cv2.resize( watermark, ( 100, 100 * watermark.shape[0]/watermark.shape[1] ) )
				
				self._watermarkShape = watermark.shape
				
				watermarkMask = cv2.cvtColor(watermark, cv2.COLOR_BGR2GRAY) / 255.0
				watermarkMask = np.repeat( watermarkMask, 3).reshape( (self._watermarkShape[0],self._watermarkShape[1],3) )
				self._watermakMaskWeighted = watermarkMask * watermark
				self._watermarkInverted = 1.0 - watermarkMask
				return True

			else:
				self.close_camera()
			
		return False

	def close_camera(self):
		if self._camera:
			self._camera.release()
			self._camera = None

		self._watermakMaskWeighted = None
		self._watermarkInverted = None
		self._infoArea = None

	def list_camera_info(self):
		result = []

		if os.path.exists(self._camerasDir):
			cameras = os.listdir(self._camerasDir)
			for c in cameras:
				with open(os.path.join(self._camerasDir, c ,'name'), 'r') as name_file:
					result.append({
						'id': c,
						'name': name_file.read().replace('\n', '')
					})

		return result

	def list_devices(self):
		if os.path.exists(self._camerasDir): 
			return os.listdir(self._camerasDir)
		else:
			return []

	def get_pic(self, text=None):
		img = self._snapshot_from_camera()

		if img != None:
			if text:
				self._apply_watermark(img, text)

			return cv2.cv.EncodeImage('.jpeg', cv2.cv.fromarray(img), [cv2.cv.CV_IMWRITE_JPEG_QUALITY, 75]).tostring()
		else:
			return None

	def save_pic(self, filename, text=None):
		img = self._snapshot_from_camera()
		if img != None:
			if text:
				self._apply_watermark(img, text)

			return cv2.imwrite(filename, img)

	def isCameraAvailable(self):
		return self._camera != None and self._camera.isOpened()

	def _snapshot_from_camera(self):
		if not self._camera:
			if not self.open_camera():
				self._logger.error('Not able to open camera')
				return None

		#discard some frames buffered by the camera
		for i in range(5):
			self._camera.grab()

		try:
			retval, img = self._camera.retrieve()

		except:
			retval = None

		if retval:
			return img

		self._logger.error('Not able to read image from camera')
		return None

	def _apply_watermark(self, img, text):
		if text and img != None:
			imgPortion = img[-(self._watermarkShape[0]+5):-5, -(self._watermarkShape[1]+5):-5]
			img[-(self._watermarkShape[0]+5):-5, -(self._watermarkShape[1]+5):-5] = (self._watermarkInverted * imgPortion) + self._watermakMaskWeighted

			img[:self._infoAreaShape[0], :self._infoAreaShape[1]] = self._infoArea
			cv2.putText(img, text, (30,17), cv2.FONT_HERSHEY_PLAIN, 1.0, (81,82,241), thickness=1)

			return True

		return False
