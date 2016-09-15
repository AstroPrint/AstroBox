# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from octoprint.settings import settings

# singleton
_instance = None

def cameraManager():
	global _instance
	if _instance is None:
		if platform == "linux" or platform == "linux2":
			number_of_video_device = 0 #/dev/video``0´´

			manager = settings().get(['camera', 'manager'])

			if manager == 'gstreamer':
				try:
					from astroprint.camera.v4l2.gstreamer import GStreamerManager
					_instance = GStreamerManager(number_of_video_device)

				except ImportError, ValueError:
					#another manager was selected or the gstreamer library is not present on this
					#system, in that case we pick a mjpeg manager

					_instance = None
					s = settings()
					s.set(['camera', 'manager'], 'mjpeg')
					s.save()

			if _instance is None:
				from astroprint.camera.v4l2.mjpeg import MjpegManager
				_instance = MjpegManager(number_of_video_device)

		elif platform == "darwin":
			from astroprint.camera.mac import CameraMacManager
			_instance = CameraMacManager()

	return _instance

import threading
import os.path
import time
import logging

from sys import platform

from octoprint.events import eventManager, Events
from astroprint.cloud import astroprintCloud
from astroprint.printer.manager import printerManager

class TimelapseWorker(threading.Thread):
	def __init__(self, manager, timelapseId, timelapseFreq):
		super(TimelapseWorker, self).__init__()

		self._stopExecution = False
		self._cm = manager
		self._resumeFromPause = threading.Event()

		self.daemon = True
		self.timelapseId = timelapseId
		self.timelapseFreq = timelapseFreq

	def run(self):
		lastUpload = 0
		self._resumeFromPause.set()
		while not self._stopExecution:
			if (time.time() - lastUpload) >= self.timelapseFreq and self._cm.addPhotoToTimelapse(self.timelapseId):
				lastUpload = time.time()

			time.sleep(1)
			self._resumeFromPause.wait()

	def stop(self):
		self._stopExecution = True
		if self.isPaused():
			self.resume()

		self.join()

	def pause(self):
		self._resumeFromPause.clear()

	def resume(self):
		self._resumeFromPause.set()

	def isPaused(self):
		return not self._resumeFromPause.isSet()

class CameraManager(object):
	name = None

	def __init__(self,cameraInfo=None):

		#RECTIFYNIG default settings

		s = settings()

		self._settings = {
			'encoding': s.get(["camera", "encoding"]),
			'size': s.get(["camera", "size"]),
			'framerate': s.get(["camera", "framerate"])
		}

		self._eventManager = eventManager()

		self.timelapseWorker = None
		self.timelapseInfo = None

		self.videoType = settings().get(["camera", "encoding"])
		self.videoSize = settings().get(["camera", "size"])
		self.videoFramerate = settings().get(["camera", "framerate"])
		self.open_camera()

	def shutdown(self):
		self._logger.info('Shutting Down CameraManager')
		self.close_camera()

		if self.timelapseWorker:
			self.timelapseWorker.stop()
			self.timelapseWorker = None

		global _instance
		_instance = None

	def addPhotoToTimelapse(self, timelapseId):
		#Build text
		printerData = printerManager().getCurrentData()
		text = "%d%% - Layer %s%s" % (
			printerData['progress']['completion'],
			str(printerData['progress']['currentLayer']) if printerData['progress']['currentLayer'] else '--',
			"/%s" % str(printerData['job']['layerCount'] if printerData['job']['layerCount'] else '')
		)

		picBuf = self.get_pic(text=text)

		if picBuf:
			picData = astroprintCloud().uploadImageFile(timelapseId, picBuf)
			#we need to check again as it's possible that this was the last
			#pic and the timelapse is closed.
			if picData and self.timelapseInfo:
				self.timelapseInfo['last_photo'] = picData['url']
				self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)
				return True

		return False

	def start_timelapse(self, freq):
		if freq == '0':
			return False

		if self.timelapseWorker:
			self.stop_timelapse()

		#check that there's a print ongoing otherwise don't start
		selectedFile = printerManager()._selectedFile
		if not selectedFile:
			return False

		if not self.isCameraConnected():
			if not self.open_camera():
				return False

		timelapseId = astroprintCloud().startPrintCapture(os.path.split(selectedFile["filename"])[1])
		if timelapseId:
			self.timelapseInfo = {
				'id': timelapseId,
				'freq': freq,
				'paused': False,
				'last_photo': None
			}

			if freq == 'layer':
				# send first pic and subscribe to layer change events
				self.addPhotoToTimelapse(timelapseId)
				self._eventManager.subscribe(Events.LAYER_CHANGE, self._onLayerChange)

			else:
				try:
					freq = float(freq)
				except ValueError:
					return False

				self.timelapseInfo['freq'] = freq
				self.timelapseWorker = TimelapseWorker(self, timelapseId, freq)
				self.timelapseWorker.start()

			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)

			return True

		return False

	def update_timelapse(self, freq):
		if self.timelapseInfo and self.timelapseInfo['freq'] != freq:
			if freq == 'layer':
				if self.timelapseWorker and not self.timelapseWorker.isPaused():
					self.pause_timelapse();

				# subscribe to layer change events
				self._eventManager.subscribe(Events.LAYER_CHANGE, self._onLayerChange)
			else:
				try:
					freq = float(freq)
				except ValueError:
					return False

				# if subscribed to layer change events, unsubscribe here
				self._eventManager.unsubscribe(Events.LAYER_CHANGE, self._onLayerChange)

				if freq == 0:
					self.pause_timelapse()
				elif not self.timelapseWorker:
					self.timelapseWorker = TimelapseWorker(self, self.timelapseInfo['id'], freq)
					self.timelapseWorker.start()
				elif self.timelapseWorker.isPaused():
					self.timelapseWorker.timelapseFreq = freq
					self.resume_timelapse()
				else:
					self.timelapseWorker.timelapseFreq = freq

			self.timelapseInfo['freq'] = freq
			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)

			return True

		return False

	def stop_timelapse(self, takeLastPhoto = False):
		#unsubscribe from layer change events
		self._eventManager.unsubscribe(Events.LAYER_CHANGE, self._onLayerChange)
		self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, None)

		if self.timelapseWorker:
			self.timelapseWorker.stop()
			self.timelapseWorker = None

		if takeLastPhoto and self.timelapseInfo:
			self.addPhotoToTimelapse(self.timelapseInfo['id'])

		self.timelapseInfo = None

		return True

	def pause_timelapse(self):
		if self.timelapseWorker and not self.timelapseWorker.isPaused():
			self.timelapseWorker.pause()
			self.timelapseInfo['paused'] = True
			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)
			return True

		return False

	def resume_timelapse(self):
		if self.timelapseWorker and self.timelapseWorker.isPaused():
			self.timelapseWorker.resume()
			self.timelapseInfo['paused'] = False
			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)
			return True

		return False

	def settingsChanged(self, cameraSettings):
		self._settings = cameraSettings

	def open_camera(self):
		return False

	def close_camera(self):
		pass

	def start_video_stream(self):
		pass

	def stop_video_stream(self):
		pass

	def list_camera_info(self):
		pass

	def list_devices(self):
		pass

	def get_pic(self, text=None):
		pass

	def get_pic_async(self, done, text=None):
		pass

	def save_pic(self, filename, text=None):
		pass

	def settingsStructure(self):
		return {}

	#Whether a camera device exists in the platform
	def isCameraConnected(self):
		return False

	#Whether the camera properties have been read
	def hasCameraProperties(self):
		return False

	#Initiate a process to look for connected cameras
	def reScan(self):
		return False

	def isResolutionSupported(self, resolution):
		pass

	# starts a client session on the camera manager, starts streaming if first session. Returns True on succcess
	def startLocalVideoSession(self, sessionId):
		pass

	# closes a client session on the camera manager, when no more sessions stop streaming. Returns True on success
	def closeLocalVideoSession(self, sessionId):
		pass

	@property
	def capabilities(self):
		return []

	## private functions

	def _onLayerChange(self, event, payload):
		if self.timelapseInfo:
			self.addPhotoToTimelapse(self.timelapseInfo['id'])
