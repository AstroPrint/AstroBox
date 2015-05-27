# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import time
import copy
import os
import logging

from collections import deque

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from astroprint.cloud import astroprintCloud
from astroprint.printerprofile import printerProfileManager
from astroprint.camera import cameraManager
from astroprint.printfiles.map import printFileManagerMap
from astroprint.printfiles import FileDestinations


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
	_printAfterSelect = False
	_currentZ = None
	_progress = None
	_printTime = None
	_printTimeLeft = None
	_currentLayer = None
	_fileManagerClass = None
	_currentPrintJobId = None

	def __init__(self):
		self._profileManager = printerProfileManager()

		self._fileManager= printFileManagerMap[self._fileManagerClass.name]()
		self._fileManager.registerCallback(self)
		self._state = self.STATE_NONE
		self._logger = logging.getLogger(__name__)

		self._temp = {}
		self._bedTemp = None
		self._temps = deque([], 300)

		self._messages = deque([], 300)

		self._cameraManager = cameraManager()

		# callbacks
		self._callbacks = []
		#self._lastProgressReport = None

		self._stateMonitor = StateMonitor(
			ratelimit= 1.0,
			updateCallback= self._sendCurrentDataCallbacks,
			addTemperatureCallback= self._sendAddTemperatureCallbacks,
			addLogCallback= self._sendAddLogCallbacks,
			addMessageCallback= self._sendAddMessageCallbacks
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

	@property
	def fileManager(self):
		return self._fileManager

	def rampdown(self):
		self.disconnect()
		eventManager().unsubscribe(Events.METADATA_ANALYSIS_FINISHED, self.onMetadataAnalysisFinished);
		self._callbacks = []
		self._stateMonitor.stop()
		self._stateMonitor._worker.join()
		self._fileManager.rampdown()

	def getConnectionOptions(self):
		"""
		 Retrieves the available ports, baudrates, prefered port and baudrate for connecting to the printer.
		"""
		return {
			"ports": self.serialList(),
			"baudrates": self.baudrateList(),
			"portPreference": settings().get(["serial", "port"]),
			"baudratePreference": settings().getInt(["serial", "baudrate"]),
			"autoconnect": settings().getBoolean(["serial", "autoconnect"])
		}

	def registerCallback(self, callback):
		self._callbacks.append(callback)
		self._sendInitialStateUpdate(callback)

	def unregisterCallback(self, callback):
		if callback in self._callbacks:
			self._callbacks.remove(callback)

	def _sendInitialStateUpdate(self, callback):
		try:
			data = self._stateMonitor.getCurrentData()
			data.update({
				"temps": list(self._temps),
				#Currently we don't want the logs to clogg the notification between box/boxrouter/browser
				#"logs": list(self._log),
				"messages": list(self._messages)
			})
			callback.sendCurrentData(data)
			#callback.sendHistoryData(data)
		except Exception, err:
			import sys
			sys.stderr.write("ERROR: %s\n" % str(err))
			pass

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

	def _setJobData(self, filename, filesize, sd):
		if filename is not None:
			self._selectedFile = {
				"filename": filename,
				"filesize": filesize,
				"sd": sd,
				"cloudId": None
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
				if self._selectedFile:
					self._selectedFile['cloudId'] = cloudId

				printFile = astroprintCloud().getPrintFile(cloudId)
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

	def setSerialDebugLogging(self, active):
		serialLogger = logging.getLogger("SERIAL")
		if active:
			serialLogger.setLevel(logging.DEBUG)
		else:
			serialLogger.setLevel(logging.CRITICAL)

	def isOperational(self):
		return self._comm is not None and (self._state == self.STATE_OPERATIONAL or self._state == self.STATE_PRINTING or self._state == self.STATE_PAUSED)

	def isClosedOrError(self):
		return self._comm is None or self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR or self._state == self.STATE_CLOSED

	def isError(self):
		return self._state != self.STATE_CONNECTING and (self._comm is None or self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR)

	def isBusy(self):
		return self.isPrinting() or self.isPaused()

	def isPaused(self):
		return self._state == self.STATE_PAUSED

	def isPrinting(self):
		return self._state == self.STATE_PRINTING

	def isCameraConnected(self):
		return self._cameraManager.isCameraAvailable()

	def _setCurrentZ(self, currentZ):
		self._currentZ = currentZ
		self._stateMonitor.setCurrentZ(self._currentZ)

	def _setProgressData(self, progress, filepos, printTime, printTimeLeft, currentLayer):
		self._progress = progress
		self._printTime = printTime
		self._printTimeLeft = printTimeLeft
		self._currentLayer = currentLayer

		self._stateMonitor.setProgress({
			"completion": self._progress * 100 if self._progress is not None else None,
			"currentLayer": self._currentLayer,
			"filepos": filepos,
			"printTime": int(self._printTime) if self._printTime is not None else None,
			"printTimeLeft": int(self._printTimeLeft * 60) if self._printTimeLeft is not None else None
		})

	def startPrint(self):
		"""
		 Starts the currently loaded print job.
		 Only starts if the printer is connected and operational, not currently printing and a printjob is loaded
		"""
		if not self.isConnected() or not self.isOperational() or self.isPrinting():
			return False

		if self._selectedFile is None:
			return False

		self._setCurrentZ(None)
		self._cameraManager.open_camera()

		kwargs = {
			'print_file_name': os.path.basename(self._selectedFile['filename'])
		}

		if self._selectedFile['cloudId']:
			kwargs['print_file_id'] = self._selectedFile['cloudId']

		#tell astroprint that we started a print
		result = astroprintCloud().print_job(**kwargs)

		if result and "id" in result:
			self._currentPrintJobId = result['id']

		return True

	def cancelPrint(self, disableMotorsAndHeater=True):
		"""
		 Cancel the current printjob.
		"""
		if self._comm is None:
			return False

		self._cameraManager.stop_timelapse()

		if self._currentPrintJobId:
			astroprintCloud().print_job(self._currentPrintJobId, status='failed')
			self._currentPrintJobId = None

		return True

	def togglePausePrint(self):
		"""
		 Pause the current printjob.
		"""
		if self._comm is None:
			return

		wasPaused = self.isPaused()

		self.setPause(not wasPaused)

		#the functions already check if there's a timelapse in progress
		if wasPaused:
			self._cameraManager.resume_timelapse()
		else:
			self._cameraManager.pause_timelapse()

	#~~~ Printer callbacks ~~~

	def mcPrintjobDone(self):
		#stop timelapse if there was one
		self._cameraManager.stop_timelapse(True)
		
		#Not sure if this is the best way to get the layer count
		self._setProgressData(1.0, self._selectedFile["filesize"], self.getPrintTime(), 0, self._layerCount)
		self._stateMonitor.setState({"state": self._state, "stateString": self.getStateString(), "flags": self._getStateFlags()})

		if self._currentPrintJobId:
			astroprintCloud().print_job(self._currentPrintJobId, status='success')
			self._currentPrintJobId = None

	def mcZChange(self, newZ):
		"""
		 Callback method for the comm object, called upon change of the z-layer.
		"""
		oldZ = self._currentZ
		if newZ != oldZ:
			# we have to react to all z-changes, even those that might "go backward" due to a slicer's retraction or
			# anti-backlash-routines. Event subscribes should individually take care to filter out "wrong" z-changes
			eventManager().fire(Events.Z_CHANGE, {"new": newZ, "old": oldZ})

		self._setCurrentZ(newZ)

	def mcLayerChange(self, layer):
		eventManager().fire(Events.LAYER_CHANGE, {"layer": layer})
		self._currentLayer = layer;

	def mcTempUpdate(self, temp, bedTemp):
		self._addTemperatureData(temp, bedTemp)

	def mcProgress(self):
		"""
		 Callback method for the comm object, called upon any change in progress of the printjob.
		 Triggers storage of new values for printTime, printTimeLeft and the current progress.
		"""

		#Calculate estimated print time left
		printTime = self.getPrintTime()
		progress = self.getPrintProgress()
		estimatedTimeLeft = None

		if printTime and progress and self._estimatedPrintTime:
			if progress < 1.0:
				estimatedTimeLeft = self._estimatedPrintTime * ( 1.0 - progress );
				elaspedTimeVariance = printTime - ( self._estimatedPrintTime - estimatedTimeLeft );
				adjustedEstimatedTime = self._estimatedPrintTime + elaspedTimeVariance;
				estimatedTimeLeft = ( adjustedEstimatedTime * ( 1.0 -  progress) ) / 60;

		elif self._estimatedPrintTime:
			estimatedTimeLeft = self._estimatedPrintTime / 60

		self._setProgressData(progress, self.getPrintFilepos(), printTime, estimatedTimeLeft, self._currentLayer)

	def mcHeatingUpUpdate(self, value):
		self._stateMonitor._state['flags']['heatingUp'] = value

	#~~~ Data processing functions ~~~

	def _addTemperatureData(self, temp, bedTemp):
		currentTimeUtc = int(time.time())

		data = {
			"time": currentTimeUtc
		}
		for tool in temp.keys():
			data["tool%d" % tool] = {
				"actual": temp[tool][0],
				"target": temp[tool][1]
			}
		if bedTemp is not None and isinstance(bedTemp, tuple):
			data["bed"] = {
				"actual": bedTemp[0],
				"target": bedTemp[1]
			}

		self._temps.append(data)

		self._temp = temp
		self._bedTemp = bedTemp

		self._stateMonitor.addTemperature(data)

	#~~ callback from metadata analysis event

	def onMetadataAnalysisFinished(self, event, data):
		if self._selectedFile:
			self._setJobData(self._selectedFile["filename"],
							 self._selectedFile["filesize"],
							 self._selectedFile["sd"])

	# ~~~ File Management ~~~~

	def selectFile(self, filename, sd, printAfterSelect=False):
		if not self.isConnected() or self.isBusy() or self.isStreaming():
			self._logger.info("Cannot load file: printer not connected or currently busy")
			return False

		self._printAfterSelect = printAfterSelect
		self._setProgressData(0, None, None, None, 1)
		self._setCurrentZ(None)
		return True

	def unselectFile(self):
		if not self.isConnected() and (self.isBusy() or self.isStreaming()):
			return False

		self._setProgressData(0, None, None, None, 1)
		self._setCurrentZ(None)
		return True

	# ~~~ State functions ~~~

	def getCurrentJob(self):
		currentData = self._stateMonitor.getCurrentData()
		return currentData["job"]

	def getCurrentData(self):
		return self._stateMonitor.getCurrentData()

	# ~~~ Implement this API ~~~

	def serialList(self):
		raise NotImplementedError()

	def baudrateList(self):
		raise NotImplementedError()

	def connect(self, port=None, baudrate=None):
		raise NotImplementedError()

	def isConnected(self):
		raise NotImplementedError()

	def disconnect(self):
		raise NotImplementedError()

	def isReady(self):
		raise NotImplementedError()

	def isPaused(self):
		raise NotImplementedError()

	def setPause(self, paused):
		raise NotImplementedError()

	def isHeatingUp(self):
		raise NotImplementedError()

	def isStreaming(self):
		raise NotImplementedError()

	def getStateString(self):
		raise NotImplementedError()

	def getPrintTime(self):
		raise NotImplementedError()

	def getPrintProgress(self):
		raise NotImplementedError()

	def getPrintFilepos(self):
		raise NotImplementedError()

	def getCurrentConnection(self):
		raise NotImplementedError()

	def jog(self, axis, amount):
		raise NotImplementedError()

	def home(self, axes):
		raise NotImplementedError()

	def fan(self, tool, speed):
		raise NotImplementedError()

	def extrude(self, tool, amount, speed=None):
		raise NotImplementedError()

	def setTemperature(self, type, value):
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
		self._stop = False

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

	def stop(self):
		self._stop = True
		self._changeEvent.set()

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

			if self._stop:
				#one last update
				self._updateCallback(self.getCurrentData())
				break;

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
