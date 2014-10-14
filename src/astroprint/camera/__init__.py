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
import os.path

from sys import platform
import time

from astroprint.cloud import astroprintCloud

class TimelapseWorker(threading.Thread):
	def __init__(self, manager, printer, timelapseId, timelapseFreq):
		super(TimelapseWorker, self).__init__()

		self._stopExecution = False
		self._cm = manager
		self._printer = printer

		self.daemon = True
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

				picBuf = self._cm.get_pic(text=text)

				if picBuf and self._cm._astroprint.uploadImageFile(self.timelapseId, picBuf):
					lastUpload = time.time()

			time.sleep(1)

	def stop(self):
		self._stopExecution = True
		self.join()

class CameraManager(object):
	def __init__(self):
		self._astroprint = astroprintCloud()
		self._timelapseId = None
		self._printer = None

		self.activeTimelapse = None

	def start_timelapse(self, freq):
		if not self._printer:
			from octoprint.server import printer
			self._printer = printer


		if self.activeTimelapse:
			self.stop_timelapse()

		#check that there's a print ongoing otherwise don't start
		if not self._printer._selectedFile:
			return False

		if not self.isCameraAvailable():
			if not self.open_camera():
				return False

		self._timelapseId = self._astroprint.startTimelapse(os.path.split(self._printer._selectedFile["filename"])[1])
		return self._start_timelapse_worker(freq)

	def update_timelapse(self, freq):
		if self.activeTimelapse:
			self.activeTimelapse.timelapseFreq = freq
			return True

		return False

	def stop_timelapse(self):
		if self.activeTimelapse:
			self.activeTimelapse.stop()
			self.activeTimelapse = None
			self._timelapseId = None

		return True

	def pause_timelapse(self):
		if self.activeTimelapse and self.activeTimelapse.isAlive():
			self.activeTimelapse.stop()
			return True

		return False

	def resume_timelapse(self):
		if self.activeTimelapse and not self.activeTimelapse.isAlive():
			self._start_timelapse_worker(self.activeTimelapse.timelapseFreq)
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

	## Private methods
	def _start_timelapse_worker(self, freq):
		if self._timelapseId:
			self.activeTimelapse = TimelapseWorker(self, self._printer, self._timelapseId, freq)
			self.activeTimelapse.start()
			return True	

		return False	
