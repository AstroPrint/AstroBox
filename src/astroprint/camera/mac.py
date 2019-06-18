# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os.path
import glob
import logging
import threading
import uuid
import time

from threading import Event
from random import randrange
from astroprint.camera import CameraManager

class CameraMacManager(CameraManager):
	name = 'mac'

	def __init__(self):
		super(CameraMacManager, self).__init__()

		self._logger = logging.getLogger(__name__)
		self._files = [f for f in glob.glob(os.path.join(os.path.realpath(os.path.dirname(__file__)+'/../../../local'),"camera_test*.jpeg"))]
		self.cameraName = 'Test Camera'
		self._opened = False
		self._localFrame = None
		self._localPeers = []
		self.waitForPhoto = Event()
		self._logger.info('Mac Simulation Camera Manager initialized')

	def shutdown(self):
		self._logger.info('Shutting Down Mac Camera Manager')
		self._opened = False
		self._localFrame = None
		self._localPeers = []
		self.waitForPhoto = Event()

	def settingsStructure(self):
		return {
			'videoEncoding': [{"label": "H.264", "value": "h264"}, {"label": "VP8", "value": "vp8"}],
			'frameSizes': [
				{'value': '640x480', 'label': 'Low (640 x 480)'},
				{'value': '1280x720', 'label': 'High (1280 x 720)'}
			],
			'fps': [
				{'value': '5', 'label': '5 fps'},
				{'value': '10', 'label': '10 fps'}
			],
			'cameraOutput': [
				{'value': 'files', 'label': 'Files'}
			],
			"video_rotation": [
				{"label": "No Rotation", "value": "0"},
				{"label": "Rotate 90 degrees to the right", "value": "1"},
				{"label": "Rotate 90 degrees to the left", "value": "3"},
				{"label": "Flip horizontally", "value": "4"},
				{"label": "Flip vertically", "value": "5"}
			]
		}

	def _doOpenCamera(self):
		self._opened = True
		return True

	def _doCloseCamera(self):
		self._opened = False
		return True

	def _doGetPic(self, done, text=None):
		if self.isCameraConnected():
			threading.Timer(3.0, self._simulateGetPicAsync,[done, text]).start()
		else:
			done(None)

	@property
	def capabilities(self):
		#return ['videoStreaming']
		return []

	def isCameraConnected(self):
		return True

	def hasCameraProperties(self):
		return True

	def isCameraOpened(self):
		return self._opened

	def isResolutionSupported(self, resolution):
		return resolution == '640x480'

	def _simulateGetPicAsync(self, done, text):
		fileCount = len(self._files)
		image = None

		if fileCount:
			imageFile = self._files[randrange(fileCount)]
			with open(imageFile, "r") as f:
				image = f.read()

		done(image)

	def reScan(self, broadcastChange = True):
		return True

	def isVideoStreaming(self):
		return False

	def removeLocalPeerReq(self,id):
		self._localPeers.remove(id)

		if len(self._localPeers) <= 0:
			self.stop_local_video_stream()
			self._logger.info('There are 0 local peers left')

	def addLocalPeerReq(self):
		id = uuid.uuid4().hex

		self._localPeers.append(id)

		self._logger.debug('number of local peers: %d' % len(self._localPeers))

		if len(self._localPeers) == 1:
			self.start_local_video_stream()

		return id

	def localSessionAlive(self,id):
		return id in self._localPeers

	def getFrame(self,id):
		self.waitForPhoto.wait(2)
		if self.waitForPhoto.isSet():
			self.waitForPhoto.clear()
			if id in self._localPeers:
				return self._localFrame
		else:#auto set after time
			self.removeLocalPeerReq(id)
			self.waitForPhoto.clear()
			return None

	def _responsePeersReq(self,photoData):
		self._localFrame = photoData

	def _onFrameTakenCallback(self,photoData):

		if photoData:

			if not self._localPeers:
				self.stop_local_video_stream()

			self._responsePeersReq(photoData)

			self.waitForPhoto.set()

	def start_local_video_stream(self):

		fileCount = len(self._files)

		if fileCount:

			def imagesProducer():

				while len(self._localPeers) > 0:

					time.sleep(0.5)

					def getRandomImg():
						imageFile = self._files[randrange(fileCount)]
						with open(imageFile, "r") as f:
							image = f.read()

						self._onFrameTakenCallback(image)

					threading.Timer(0, getRandomImg).start()

			threading.Timer(0, imagesProducer).start()

		return

	def stop_local_video_stream(self):
		self._localPeers = []
