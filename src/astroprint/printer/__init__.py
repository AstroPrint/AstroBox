# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import time
import serial.tools.list_ports

from sys import platform

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from astroprint.camera import cameraManager

from usbid.device import device_list

def serialList():
	ports = {}
	if platform.startswith('linux'):
		for p in device_list():
			if p.tty:
				ports['/dev/%s' % p.tty] = p.nameProduct

	else:
		for p in serial.tools.list_ports.comports():
			if p[1] != 'n/a':
				ports[p[0]] = p[1]

	return ports

def baudrateList():
	ret = [250000, 230400, 115200, 57600, 38400, 19200, 9600]
	prev = settings().getInt(["serial", "baudrate"])
	if prev in ret:
		ret.remove(prev)
		ret.insert(0, prev)
	return ret

class Printer(object):
	STATE_NONE = 0
	STATE_OPEN_SERIAL = 1
	STATE_DETECT_SERIAL = 2
	STATE_DETECT_BAUDRATE = 3
	STATE_CONNECTING = 4
	STATE_OPERATIONAL = 5
	STATE_PRINTING = 6
	STATE_PAUSED = 7
	STATE_CLOSED = 8
	STATE_ERROR = 9
	STATE_CLOSED_WITH_ERROR = 10
	STATE_TRANSFERING_FILE = 11

	driverName = None
	_fileManager = None
	_comm = None
	_selectedFile = None

	@staticmethod
	def getConnectionOptions():
		"""
		 Retrieves the available ports, baudrates, prefered port and baudrate for connecting to the printer.
		"""
		return {
			"ports": serialList(),
			"baudrates": baudrateList(),
			"portPreference": settings().get(["serial", "port"]),
			"baudratePreference": settings().getInt(["serial", "baudrate"]),
			"autoconnect": settings().getBoolean(["serial", "autoconnect"])
		}

	def __init__(self, fileManager):
		self._fileManager= fileManager
		self._fileManager.registerCallback(self)
		self._state = self.STATE_NONE

		self._cameraManager = cameraManager()

		# callbacks
		self._callbacks = []
		#self._lastProgressReport = None

		self._stateMonitor = StateMonitor(
			ratelimit=1.0,
			updateCallback=self._sendCurrentDataCallbacks,
			addTemperatureCallback=self._sendAddTemperatureCallbacks,
			addLogCallback=self._sendAddLogCallbacks,
			addMessageCallback=self._sendAddMessageCallbacks
		)
		self._stateMonitor.reset(
			state={"text": self.getStateString(), "flags": self._getStateFlags()},
			jobData={
				"file": {
					"name": None,
					"size": None,
					"origin": None,
					"date": None
				},
				"estimatedPrintTime": None,
				"filament": {
					"length": None,
					"volume": None
				}
			},
			progress={"completion": None, "filepos": None, "printTime": None, "printTimeLeft": None},
			currentZ=None
		)

		eventManager().subscribe(Events.METADATA_ANALYSIS_FINISHED, self.onMetadataAnalysisFinished);


	def __del__(self):
		self._fileManager.unregisterCallback(self)

	def _sendCurrentDataCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.sendCurrentData(copy.deepcopy(data))
			except: pass

	def _sendAddTemperatureCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.addTemperature(data)
			except: pass

	def _sendAddLogCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.addLog(data)
			except: pass

	def _sendAddMessageCallbacks(self, data):
		for callback in self._callbacks:
			try: callback.addMessage(data)
			except: pass

	def _getStateFlags(self):
		return {
			"operational": self.isOperational(),
			"printing": self.isPrinting(),
			"closedOrError": self.isClosedOrError(),
			"error": self.isError(),
			"paused": self.isPaused(),
			"ready": self.isReady(),
			"heatingUp": self.isHeatingUp(),
			"camera": self.isCameraConnected()
		}

	def _setJobData(self, filename, filesize):
		if filename is not None:
			self._selectedFile = {
				"filename": filename,
				"filesize": filesize
			}
		else:
			self._selectedFile = None

		estimatedPrintTime = None
		date = None
		filament = None
		layerCount = None
		cloudId = None

		if filename:
			# Use a string for mtime because it could be float and the
			# javascript needs to exact match
			date = int(os.stat(filename).st_ctime)

			fileData = self._fileManager.getFileData(filename)
			if fileData is not None and "gcodeAnalysis" in fileData.keys():
				fileDataProps = fileData["gcodeAnalysis"].keys()
				if "print_time" in fileDataProps:
					estimatedPrintTime = fileData["gcodeAnalysis"]["print_time"]
				if "filament_lenght" in fileDataProps:
					filament = fileData["gcodeAnalysis"]["filament_length"]
				if "layer_count" in fileDataProps:
					layerCount = fileData["gcodeAnalysis"]['layer_count']

		cloudId = self._fileManager.getFileCloudId(filename)
		renderedIimage = None
		if cloudId:
			printFile = self._astroprintCloud.getPrintFile(cloudId)
			if printFile:
				renderedIimage = printFile['images']['square']

		self._stateMonitor.setJobData({
			"file": {
				"name": os.path.basename(filename) if filename is not None else None,
				"origin": FileDestinations.LOCAL,
				"size": filesize,
				"date": date,
				"cloudId": cloudId,
				"rendered_image": renderedIimage
			},
			"estimatedPrintTime": estimatedPrintTime,
			"layerCount": layerCount,
			"filament": filament,
		})

		self._layerCount = layerCount
		self._estimatedPrintTime = estimatedPrintTime

	def isOperational(self):
		return self._comm is not None and (self._state == self.STATE_OPERATIONAL or self._state == self.STATE_PRINTING or self._state == self.STATE_PAUSED)

	def isClosedOrError(self):
		return self._comm is None or self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR or self._state == self.STATE_CLOSED

	def isError(self):
		return self._comm is None or self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR

	def isPaused(self):
		return self._state == self.STATE_PAUSED

	def isPrinting(self):
		return self._state == self.STATE_PRINTING

	def isCameraConnected(self):
		return self._cameraManager.isCameraAvailable()

	#~~ callback from metadata analysis event

	def onMetadataAnalysisFinished(self, event, data):
		if self._selectedFile:
			self._setJobData(self._selectedFile["filename"],
							 self._selectedFile["filesize"])

	# ~~~ Implement this API ~~~

	def connect(self, port=None, baudrate=None):
		raise NotImplementedError()

	def disconnect(self):
		raise NotImplementedError()

	def isReady(self):
		raise NotImplementedError()

	def isHeatingUp(self):
		raise NotImplementedError()

	def getStateString(self):
		raise NotImplementedError()

	def getCurrentConnection(self):
		raise NotImplementedError()

	def jog(self, axis, amount):
		raise NotImplementedError()

	def home(self, axes):
		raise NotImplementedError()


class StateMonitor(object):
	def __init__(self, ratelimit, updateCallback, addTemperatureCallback, addLogCallback, addMessageCallback):
		self._ratelimit = ratelimit
		self._updateCallback = updateCallback
		self._addTemperatureCallback = addTemperatureCallback
		self._addLogCallback = addLogCallback
		self._addMessageCallback = addMessageCallback

		self._state = None
		self._jobData = None
		self._gcodeData = None
		self._sdUploadData = None
		self._currentZ = None
		self._progress = None

		self._offsets = {}

		self._changeEvent = threading.Event()

		self._lastUpdate = time.time()
		self._worker = threading.Thread(target=self._work)
		self._worker.daemon = True
		self._worker.start()

	def reset(self, state=None, jobData=None, progress=None, currentZ=None):
		self.setState(state)
		self.setJobData(jobData)
		self.setProgress(progress)
		self.setCurrentZ(currentZ)

	def addTemperature(self, temperature):
		self._addTemperatureCallback(temperature)
		self._changeEvent.set()

	def addLog(self, log):
		self._addLogCallback(log)
		self._changeEvent.set()

	def addMessage(self, message):
		self._addMessageCallback(message)
		self._changeEvent.set()

	def setCurrentZ(self, currentZ):
		self._currentZ = currentZ
		self._changeEvent.set()

	def setState(self, state):
		self._state = state
		self._changeEvent.set()

	def setJobData(self, jobData):
		self._jobData = jobData
		self._changeEvent.set()

	def setProgress(self, progress):
		self._progress = progress
		self._changeEvent.set()

	def setTempOffsets(self, offsets):
		self._offsets = offsets
		self._changeEvent.set()

	def _work(self):
		while True:
			self._changeEvent.wait()

			now = time.time()
			delta = now - self._lastUpdate
			additionalWaitTime = self._ratelimit - delta
			if additionalWaitTime > 0:
				time.sleep(additionalWaitTime)

			data = self.getCurrentData()
			self._updateCallback(data)
			self._lastUpdate = time.time()
			self._changeEvent.clear()

	def getCurrentData(self):
		return {
			"state": self._state,
			"job": self._jobData,
			"currentZ": self._currentZ,
			"progress": self._progress,
			"offsets": self._offsets
		}
