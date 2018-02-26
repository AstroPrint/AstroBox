# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"


import threading
import logging
import time
import os

from astroprint.printfiles.gcode import PrintFileManagerGcode
from astroprint.printer import Printer
from astroprint.printfiles import FileDestinations
from astroprint.printerprofile import printerProfileManager
from octoprint.events import eventManager, Events
from octoprint.settings import settings
from astroprint.printer.manager import printerManager

class PrinterVirtual(Printer):
	driverName = 'virtual'
	allowTerminal = True

	_fileManagerClass = PrintFileManagerGcode

	def __init__(self):
		seettings_file = "%s/virtual-printer-settings.yaml" % os.path.dirname(settings()._configfile)
		self._previousSelectedTool = 0
		self._currentSelectedTool = 0

		self._settings = {
			'connection': 1.0,
			'heatingUp': 2.0,
			'printJob': 10.0
		}

		if os.path.isfile(seettings_file):
			import yaml

			config = None
			with open(seettings_file, "r") as f:
				config = yaml.safe_load(f)

			def merge_dict(a,b):
				for key in b:
					if isinstance(b[key], dict):
						merge_dict(a[key], b[key])
					else:
						a[key] = b[key]

			if config:
				merge_dict(self._settings, config)

		self._printing = False
		self._heatingUp = False
		self._heatingUpTimer = None
		self._temperatureChanger = None
		self._printJob = None
		self.selectedTool = 0
		self._logger = logging.getLogger(__name__)
		super(PrinterVirtual, self).__init__()


	def selectFile(self, filename, sd, printAfterSelect=False):
		if not super(PrinterVirtual, self).selectFile(filename, sd, printAfterSelect):
			return False

		if sd:
			raise('Printing from SD card is not supported for the Virtual Driver')

		if not os.path.exists(filename) or not os.path.isfile(filename):
			raise IOError("File %s does not exist" % filename)
		filesize = os.stat(filename).st_size

		eventManager().fire(Events.FILE_SELECTED, {
			"file": filename,
			"origin": FileDestinations.LOCAL
		})

		self._setJobData(filename, filesize, sd)
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

		self._currentFile = {
			'filename': filename,
			'size': filesize,
			'origin': FileDestinations.LOCAL,
			'start_time': None,
			'progress': None,
			'position': None
		}

		if self._printAfterSelect:
			self.startPrint()

		return True

	def startPrint(self):
		if not super(PrinterVirtual, self).startPrint():
			return

		if not self.isOperational() or self.isPrinting():
			return

		if self._currentFile is None:
			raise ValueError("No file selected for printing")

		if self._printJob and self._printJob.isAlive():
			raise Exception("A Print Job is still running")

		self._changeState(self.STATE_PRINTING)
		data = printerManager().getFileInfo(self._currentFile['filename'])
		eventManager().fire(Events.PRINT_STARTED, data)

		#First we simulate heatup
		extruder_count = (printerProfileManager().data.get('extruder_count'))
		for i in range(extruder_count):
			self.setTemperature('tool'+str(i), 210)
		self.setTemperature("bed", 60)
		self.mcHeatingUpUpdate(True)
		self._heatingUp = True

		def heatupDone():
			if not self._shutdown:
				self.mcHeatingUpUpdate(False)
				self._heatingUp = False
				self._heatingUpTimer = None
				self._printJob = JobSimulator(self, self._currentFile)
				self._printJob.start()

		self._printJob = None
		self._heatingUpTimer = threading.Timer(self._settings['heatingUp'], heatupDone)
		self._heatingUpTimer.start()

	def executeCancelCommands(self, disableMotorsAndHeater):
		"""
		 Cancel the current printjob.
		"""

		if self._printJob:
			self._printJob.cancel()

		if self.isPaused:
			self.setPause(False)

		if self._heatingUpTimer:
			self._heatingUpTimer.cancel()
			self._heatingUpTimer = None
			self.mcHeatingUpUpdate(False)

			extruder_count = (printerProfileManager().data.get('extruder_count'))
			for i in range(extruder_count):
				self.setTemperature('tool'+str(i), 0)

			self.setTemperature("bed", 0)
			time.sleep(1)
			self._changeState(self.STATE_OPERATIONAL)

	def serialList(self):
		return {
			'virtual': 'Virtual Printer'
		}

	def baudrateList(self):
		return []

	def connect(self, port=None, baudrate=None):
		self._comm = True
		self._changeState(self.STATE_CONNECTING)

		def doConnect():
			if not self._shutdown:
				self._changeState(self.STATE_OPERATIONAL)
				self._temperatureChanger = TempsChanger(self)
				self._temperatureChanger.start()

				#set initial temps
				extruder_count = (printerProfileManager().data.get('extruder_count'))
				for i in range(extruder_count):
					self.setTemperature('tool'+str(i), 25)
				self.setTemperature('bed', 25)

		t = threading.Timer(self._settings['connection'], doConnect)
		t.start()

	def isConnected(self):
		return self._comm

	def disconnect(self):
		if self._printJob:
			self._printJob.cancel()

		if self._comm:
			self._comm = False

			if self._temperatureChanger:
				self._temperatureChanger.stop()
				self._temperatureChanger.join()
				self._temperatureChanger = None

			self._changeState(self.STATE_CLOSED)
			eventManager().fire(Events.DISCONNECTED)

	def isReady(self):
		return self._comm and not self.STATE_PRINTING

	def isPaused(self):
		return self._state == self.STATE_PAUSED

	def setPause(self, paused):
		printFileInfo = {
			"file": self._currentFile['filename'],
			"filename": os.path.basename(self._currentFile['filename']),
			"origin": self._currentFile['origin']
		}

		if paused:
			self._previousSelectedTool = self._currentSelectedTool
			self._changeState(self.STATE_PAUSED)
			eventManager().fire(Events.PRINT_PAUSED, printFileInfo)

		else:
			if self._currentSelectedTool != self._previousSelectedTool:
				self.mcToolChange(self._previousSelectedTool, self._currentSelectedTool)
				self._currentSelectedTool = self._previousSelectedTool

			self._changeState(self.STATE_PRINTING)
			eventManager().fire(Events.PRINT_RESUMED, printFileInfo)

		if self._printJob:
			self._printJob.setPaused(paused)

	def isHeatingUp(self):
		return self._heatingUp

	def isStreaming(self):
		return False

	def getStateString(self):
		if self._state == self.STATE_NONE:
			return "Offline"
		if self._state == self.STATE_OPEN_SERIAL:
			return "Opening serial port"
		if self._state == self.STATE_DETECT_SERIAL:
			return "Detecting serial port"
		if self._state == self.STATE_DETECT_BAUDRATE:
			return "Detecting baudrate"
		if self._state == self.STATE_CONNECTING:
			return "Connecting"
		if self._state == self.STATE_OPERATIONAL:
			return "Operational"
		if self._state == self.STATE_PRINTING:
			return "Printing"
		if self._state == self.STATE_PAUSED:
			return "Paused"
		if self._state == self.STATE_CLOSED:
			return "Closed"
		if self._state == self.STATE_ERROR:
			return "Error: %s" % (self.getShortErrorString())
		if self._state == self.STATE_CLOSED_WITH_ERROR:
			return "Error: %s" % (self.getShortErrorString())
		if self._state == self.STATE_TRANSFERING_FILE:
			return "Transfering file to SD"
		return "?%d?" % (self._state)

	def getPrintTime(self):
		if self._printJob:
			return self._printJob.printTime
		else:
			return None

	def getSelectedTool(self):
		return self.selectedTool

	def getPrintProgress(self):
		if self._printJob:
			return self._printJob.progress
		else:
			return None

	def getPrintFilepos(self):
		if self._printJob:
			return self._printJob.filePos
		else:
			return None

	def getCurrentConnection(self):
		if not self._comm:
			return "Closed", None, None

		return self.getStateString(), 'virtual', 0

	def getConsumedFilament(self):
		return self._printJob._consumedFilament if self._printJob else 0

	def getTotalConsumedFilament(self):
		return sum([self._printJob._consumedFilament[k] for k in self._printJob._consumedFilament.keys()]) if self._printJob else 0

	def jog(self, axis, amount):
		self._logger.info('Jog - Axis: %s, Amount: %s', axis, self.jogAmountWithPrinterProfile(axis, amount))

	def home(self, axes):
		self._logger.info('Home - Axes: %s', ', '.join(axes))

	def fan(self, tool, speed):
		self._logger.info('Fan - Tool: %s, Speed: %s', tool, speed)

	def extrude(self, tool, amount, speed=None):
		self._logger.info('Extrude - Tool: %s, Amount: %s, Speed: %s', tool, amount, speed)

	def changeTool(self, tool):
		previousSelectedTool = self._currentSelectedTool
		self._currentSelectedTool = tool
		self._logger.info('Change tool from %s to %s', previousSelectedTool, tool)
		self.mcToolChange(tool, previousSelectedTool)

	def setTemperature(self, type, value):
		self._logger.info('Temperature - Type: %s, Value: %s', type, value)
		if self._temperatureChanger:
			self._temperatureChanger.setTarget(type, value)

	def sendRawCommand(self, command):
		self._logger.info('Raw Command - %s', command)

	def getShortErrorString(self):
		return "Virtual Error"

	# ~~~~~~ Private Functions ~~~~~~~~~~
	def _changeState(self, newState):
		if self._state == newState:
			return

		oldState = self.getStateString()
		self._state = newState
		self._logger.info('Changing monitoring state from [%s] to [%s]' % (oldState, self.getStateString()))

		# forward relevant state changes to gcode manager
		if self._comm is not None and oldState == self.STATE_PRINTING:
			self._fileManager.resumeAnalysis() # printing done, put those cpu cycles to good use
		elif self._comm is not None and newState == self.STATE_PRINTING:
			self._fileManager.pauseAnalysis() # do not analyse gcode while printing
		elif self._comm is not None and newState == self.STATE_OPERATIONAL:
			eventManager().fire(Events.CONNECTED)
		elif self._comm is not None and newState == self.STATE_CONNECTING:
			eventManager().fire(Events.CONNECTING)

		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def printJobCancelled(self):
		# reset progress, height, print time
		self._setProgressData(None, None, None, None, None)

		# mark print as failure
		if self._currentFile is not None:
			self._fileManager.printFailed(self._currentFile["filename"], self.getPrintTime())
			self.unselectFile()

class TempsChanger(threading.Thread):
	def __init__(self, manager):
		self._stopped = False
		self._manager = manager
		self._targets = {}
		self._actuals = {}

		super(TempsChanger, self).__init__()

	def run(self):
		while not self._stopped:
			for t in self._targets.keys():
				if self._actuals[t] > self._targets[t]:
					self._actuals[t] = self._actuals[t] - 5

				elif self._actuals[t] < self._targets[t]:
					self._actuals[t] = self._actuals[t] + 5

			self._updateTemps()
			time.sleep(10)

		self._manager = None

	def stop(self):
		self._stopped = True

	def setTarget(self, type, target):
		self._targets[type] = target

		if type not in self._actuals:
			self._actuals[type] = 0

	def _updateTemps(self):
		data = { "time": int(time.time()) }

		for t in self._targets.keys():
			data[t] = {
				"actual": self._actuals[t],
				"target": self._targets[t]
			}

		eventManager().fire(Events.TEMPERATURE_CHANGE, data)
		self._manager._stateMonitor.addTemperature(data)

class JobSimulator(threading.Thread):
	def __init__(self, printerManager, currentFile):
		self._pm = printerManager
		self._file = currentFile
		self._jobLength = printerManager._settings['printJob']
		self._stopped = False
		self._timeElapsed = 0
		self._percentCompleted = 0
		self._filePos = 0
		self._currentLayer = 0
		self._pausedEvent = threading.Event()
		self._consumedFilament = {0: 0}

		super(JobSimulator, self).__init__()

	def run(self):
		self._pausedEvent.set()

		while not self._stopped and self._percentCompleted < 1:
			self._pausedEvent.wait()

			if self._stopped:
				break

			self._timeElapsed += 1
			self._filePos += 1
			self._currentLayer += 1
			self._consumedFilament[0] += 10
			self._percentCompleted = self._timeElapsed / self._jobLength
			self._pm.mcLayerChange(self._currentLayer)
			self._pm.mcProgress()

			time.sleep(1)

		self._pm._changeState(self._pm.STATE_OPERATIONAL)

		extruder_count = (printerProfileManager().data.get('extruder_count'))
		for i in range(extruder_count):
			self._pm.setTemperature('tool'+str(i), 0)
		self._pm.setTemperature('bed', 0)

		payload = {
			"file": self._file['filename'],
			"filename": os.path.basename(self._file['filename']),
			"origin": self._file['origin'],
			"time": self._timeElapsed,
			"layerCount": self._currentLayer
		}

		if self._percentCompleted >= 1:
			self._pm.mcPrintjobDone()
			self._pm._fileManager.printSucceeded(payload['filename'], payload['time'], payload['layerCount'])
			eventManager().fire(Events.PRINT_DONE, payload)
		else:
			self._pm.printJobCancelled()
			eventManager().fire(Events.PRINT_CANCELLED, payload)
			self._pm._fileManager.printFailed(payload['filename'], payload['time'])

		self._pm = None

	def cancel(self):
		self._stopped = True
		if not self._pausedEvent.isSet():
			self.setPaused(False)

	def setPaused(self, value):
		if value:
			self._pausedEvent.clear()
		else:
			self._pausedEvent.set()

	@property
	def printTime(self):
		return self._timeElapsed

	@property
	def progress(self):
		return self._percentCompleted

	@property
	def filePos(self):
		return self._filePos
