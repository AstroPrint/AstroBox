# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

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

import threading
import os.path
import time

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
	def __init__(self):
		self._eventManager = eventManager()

		self.timelapseWorker = None
		self.timelapseInfo = None
		self.open_camera()

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

		if not self.isCameraAvailable():
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

	## private functions

	def _onLayerChange(self, event, payload):
		if self.timelapseInfo:
			self.addPhotoToTimelapse(self.timelapseInfo['id'])