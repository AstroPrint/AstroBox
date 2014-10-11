# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
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

from sys import platform
import time

from astroprint.cloud import astroprintCloud

class TimelapseWorker(threading.Thread):
	def __init__(self, manager, timelapseId, timelapseFreq):
		from octoprint.server import printer

		super(TimelapseWorker, self).__init__()
		self.daemon = True
		self._stopExecution = False
		self._cm = manager
		self._printer = printer
		self.timelapseId = timelapseId
		self.timelapseFreq = float(timelapseFreq)

	def run(self):
		lastUpload = 0
		while not self._stopExecution:
			if (time.time() - lastUpload ) > self.timelapseFreq:
				#Build text
				printerData = self._printer.getCurrentData()
				text = "%d%% - Layer %d%s" % (
					printerData['progress']['completion'], 
					printerData['progress']['currentLayer'],
					("/%d" % printerData['job']['layerCount']) if printerData['job']['layerCount'] else ''
				)

				picBuf = self._cm.get_pic(text)

				if picBuf and self._cm._astroprint.uploadImageFile(self.timelapseId, picBuf):
					print 'image uploaded'
					lastUpload = time.time()

			time.sleep(1)

	def stop(self):
		self._stopExecution = True
		self.join()

class CameraManager(object):
	def __init__(self):
		self._astroprint = astroprintCloud()
		self.activeTimelapse = None

	def start_timelapse(self, freq):
		if self.activeTimelapse:
			self.stop_timelapse()

		if not self.isCameraAvailable():
			if not self.open_camera():
				return False

		timelapseId = self._astroprint.startTimelapse('test')
		if timelapseId:
			self.activeTimelapse = TimelapseWorker(self, timelapseId, freq)
			self.activeTimelapse.start()
			return True

		return False

	def update_timelapse(self, freq):
		if self.activeTimelapse:
			self.activeTimelapse.timelapseFreq = freq
			return True

		return False

	def stop_timelapse(self):
		if self.activeTimelapse:
			self.activeTimelapse.stop()
			self.activeTimelapse = None

		return True

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
