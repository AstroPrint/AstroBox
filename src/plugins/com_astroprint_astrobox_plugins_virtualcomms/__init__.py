# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os
import threading
import time

from astroprint.plugin import Plugin, PrinterCommsService, SystemEvent, PrinterState
from astroprint.printfiles.gcode import PrintFileManagerGcode

class VirtualComms(Plugin, PrinterCommsService):
	# PrinterCommsService

	def initPrinterCommsService(self, printerManager):
		super(VirtualComms, self).initPrinterCommsService(printerManager)

		seettings_file = "%s/virtual-printer-settings.yaml" % self.settingsDir
		self._previousSelectedTool = 0
		self._currentSelectedTool = 0

		self._vpSettings = {
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
				merge_dict(self._vpSettings, config)

		self._printing = False
		self._heatingUp = False
		self._heatingUpTimer = None
		self._printJob = None
		self._comm = False
		self._preheating = False
		self._temperatureChanger = None

	def connect(self, port=None, baudrate=None):
		self._comm = True
		self._changePrinterState(PrinterState.STATE_CONNECTING)

		def doConnect():
			if not self._printerManager.shuttingDown:
				self._changePrinterState(PrinterState.STATE_OPERATIONAL)
				self._temperatureChanger = TempsChanger(self)
				self._temperatureChanger.start()

				#set initial temps
				self.setTemperature('tool0', 25)
				self.setTemperature('bed', 25)

		t = threading.Timer(self._vpSettings['connection'], doConnect)
		t.start()

	def disconnect(self):
		if self._comm:
			self._comm = False

			if self._temperatureChanger:
				self._temperatureChanger.stop()
				self._temperatureChanger.join()
				self._temperatureChanger = None

			self._changePrinterState(PrinterState.STATE_CLOSED)

	def startPrint(self):
		if self._printJob and self._printJob.isAlive():
			raise Exception("A Print Job is still running")

		self._changePrinterState(PrinterState.STATE_PRINTING)

		currentFile = self._printerManager.selectedFile

		data = self._printerManager.getFileInfo(currentFile['filename'])

		self.fireSystemEvent(SystemEvent.PRINT_STARTED, data)

		#First we simulate heatup
		self.setTemperature("tool0", 210)
		self.setTemperature("bed", 60)
		self.reportHeatingUpChange(True)
		self._heatingUp = True

		def heatupDone():
			if not self._printerManager.shuttingDown:
				self.reportHeatingUpChange(False)
				self._heatingUp = False
				self._heatingUpTimer = None
				self._printJob = JobSimulator(self, self._printerManager, currentFile)
				self._printJob.start()

		self._printJob = None
		self._heatingUpTimer = threading.Timer(self._vpSettings['heatingUp'], heatupDone)
		self._heatingUpTimer.start()

	def disableMotorsAndHeater(self):
		self.setTemperature("tool0", 0)
		self.setTemperature("bed", 0)
		self._logger.info('Turning down motors')

	def executeCancelCommands(self, disableMotorsAndHeater):
		if self._printJob:
			self._printJob.cancel()

		if self.paused:
			self.setPaused(False)

		if self._heatingUpTimer:
			self._heatingUpTimer.cancel()
			self._heatingUpTimer = None
			self.reportHeatingUpChange(False)

		time.sleep(1)
		self._changePrinterState(PrinterState.STATE_OPERATIONAL)

	def jog(self, axis, amount):
		self._logger.info('Jog - Axis: %s, Amount: %s', axis, amount)

	def home(self, axes):
		self._logger.info('Home - Axes: %s', ', '.join(axes))

	def fan(self, tool, speed):
		self._logger.info('Fan - Tool: %s, Speed: %s', tool, speed)

	def extrude(self, tool, amount, speed=None):
		self._logger.info('Extrude - Tool: %s, Amount: %s, Speed: %s', tool, amount, speed)

	def changeTool(self, tool):
		self._logger.info('Change tool to %s', tool)

	def sendCommand(self, command):
		self._logger.info('Command Sent - %s', command)

	def setTemperature(self, type, value):
		self._logger.info('Temperature - Type: %s, Value: %s', type, value)
		if self._temperatureChanger:
			self._temperatureChanger.setTarget(type, value)

	def serialLoggingChanged(self):
		pass

	def getCurrentTemperatures(self):
		return {
			'tool0':
				{
					"actual": 20,
					"target": 20
				},
			'tool1':
				{
					"actual": 20,
					"target": 20
				},
			'bed':
				{
					"actual": 40,
					"target": 40
				}
			}

	@property
	def ports(self):
		return {
			'virtual': 'Virtual Printer'
		}

	@property
	def baudRates(self):
		return []

	@property
	def currentConnection(self):
		return ('virtual', None) if self._comm else (None, None)

	@property
	def settingsProperties(self):
		return {
			'customCancelCommands': True
		}

	@property
	def fileManagerClass(self):
		return PrintFileManagerGcode

	@property
	def allowTerminal(self):
		return True

	@property
	def connected(self):
		return self._comm

	@property
	def preHeating(self):
		return self._preheating

	@property
	def printProgress(self):
		if self._printJob:
			return self._printJob.progress
		else:
			return None

	@property
	def printFilePosition(self):
		if self._printJob:
			return self._printJob.filePos
		else:
			return None

	@property
	def consumedFilamentData(self):
		return self._printJob._consumedFilament if self._printJob else 0

	@property
	def consumedFilamentSum(self):
		return sum([self._printJob._consumedFilament[k] for k in self._printJob._consumedFilament.keys()]) if self._printJob else 0

	def setPaused(self, paused):
		currentFile = self._printerManager.selectedFile

		printFileInfo = {
			"file": currentFile['filename'],
			"filename": os.path.basename(currentFile['filename']),
			"origin": currentFile['origin']
		}

		if paused:
			self._changePrinterState(PrinterState.STATE_PAUSED)
			self.fireSystemEvent(SystemEvent.PRINT_PAUSED, printFileInfo)

		else:
			self._changePrinterState(PrinterState.STATE_PRINTING)
			self.fireSystemEvent(SystemEvent.PRINT_RESUMED, printFileInfo)

		if self._printJob:
			self._printJob.setPaused(paused)


class TempsChanger(threading.Thread):
	def __init__(self, plugin):
		self._stopped = False
		self._plugin = plugin
		self._targets = {};
		self._actuals = {};

		super(TempsChanger, self).__init__()

	def run(self):
		while not self._stopped:
			for t in self._targets.keys():
				if self._actuals[t] > self._targets[t]:
					self._actuals[t] = self._actuals[t] - 5

				elif self._actuals[t] < self._targets[t]:
					self._actuals[t] = self._actuals[t] + 5

			self._updateTemps()
			time.sleep(1)

		self._plugin = None

	def stop(self):
		self._stopped = True

	def setTarget(self, type, target):
		self._targets[type] = target

		if type not in self._actuals:
			self._actuals[type] = 0

	def _updateTemps(self):
		tools = {}
		bed = {}

		for t in self._targets.keys():
			if t.startswith('tool'):
				tools[int(t[4:])] = ( self._actuals[t], self._targets[t] )
			elif t.startswith('bed'):
				bed = ( self._actuals[t], self._targets[t] )

		self._plugin.reportTempChange(tools, bed)

class JobSimulator(threading.Thread):
	def __init__(self, plugin, printerManager, currentFile):
		self._pm = printerManager
		self._plugin = plugin
		self._file = currentFile
		self._stopped = False
		self._percentCompleted = 0
		self._filePos = 0
		self._pausedEvent = threading.Event()
		self._consumedFilament = {0: 0}

		super(JobSimulator, self).__init__()

	def run(self):
		self._pausedEvent.set()
		timeElapsed = 0
		currentLayer = 0
		jobLength = self._plugin._vpSettings['printJob']

		while not self._stopped and self._percentCompleted < 1:
			self._pausedEvent.wait()

			if self._stopped:
				break

			timeElapsed += 1
			currentLayer += 1

			self._filePos += 1
			self._consumedFilament[0] += 10
			self._percentCompleted = timeElapsed / jobLength
			self._plugin.reportNewLayer()
			self._plugin.reportPrintProgressChanged()

			time.sleep(1)

		self._plugin.setTemperature('tool0', 0)
		self._plugin.setTemperature('bed', 0)

		if self._percentCompleted >= 1:
			self._plugin.reportPrintJobCompleted()
		else:
			self._plugin.reportPrintJobFailed()

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
	def progress(self):
		return self._percentCompleted

	@property
	def filePos(self):
		return self._filePos

__plugin_instance__ = VirtualComms()
