# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from astroprint.printer import Printer
from astroprint.plugin import pluginManager
from astroprint.printfiles import FileDestinations

class NoPluginException(Exception):
	pass

class PrinterWithPlugin(Printer):
	driverName = 'plugin'

	def __init__(self, pluginId):
		#Register to plugin remove events
		pm = pluginManager()

		self._plugin = pm.getPlugin(pluginId)
		if self._plugin is None:
			raise NoPluginException

		self._plugin.initPrinterCommsService(self)

		pm.addEventListener('ON_PLUGIN_REMOVED', self.onPluginRemoved)

		self._currentFile = None

		super(PrinterWithPlugin, self).__init__()

	def rampdown(self):
		pluginManager().removeEventListener('ON_PLUGIN_REMOVED', self.onPluginRemoved)
		super(PrinterWithPlugin, self).rampdown()

	@property
	def allowTerminal(self):
		return self._plugin.allowTerminal

	@property
	def selectedFile(self):
		return self._currentFile

	@property
	def _fileManagerClass(self):
		return self._plugin.fileManagerClass()

	def connect(self, port=None, baudrate=None):
		if self._plugin.connect(port, baudrate):
			s = settings()
			savedPort = s.get(["serial", "port"])
			savedBaudrate = s.getInt(["serial", "baurate"])
			needsSave = False

			if port != savedPort:
				s.set(["serial", "port"], port)
				needsSave = True

			if baudrate != savedBaudrate:
				s.set(["serial", "baudrate"], baudrate)
				needsSave = True

			if needsSave:
				s.save()

			return True
		else:
			return False

	def disconnect(self):
		return self._plugin.disconnect()

	def selectFile(self, filename, sd, printAfterSelect=False):
		if not super(PrinterWithPlugin, self).selectFile(filename, sd, printAfterSelect):
			return False

		if sd and not self._plugin.allowSDCardPrinting:
			raise('Printing from SD card is not supported for the Virtual Driver')

		if not os.path.exists(filename) or not os.path.isfile(filename):
			raise IOError("File %s does not exist" % filename)

		filesize = os.stat(filename).st_size

		eventManager().fire(Events.FILE_SELECTED, {
			"file": filename,
			"origin": FileDestinations.SDCARD if sd else FileDestinations.LOCAL
		})

		self._setJobData(filename, filesize, sd)
		self.refreshStateData()

		self._currentFile = {
			'filename': filename,
			'size': filesize,
			'origin': FileDestinations.SDCARD if sd else FileDestinations.LOCAL,
			'start_time': None,
			'progress': None,
			'position': None
		}

		if self._printAfterSelect:
			self.startPrint()

		return True

	def startPrint(self):
		if not super(PrinterWithPlugin, self).startPrint():
			return

		if not self.isOperational() or self.isPrinting():
			return

		if self._currentFile is None:
			raise ValueError("No file selected for printing")

		self._plugin.startPrint()

	def executeCancelCommands(self, disableMotorsAndHeater):
		self._plugin.executeCancelCommands(disableMotorsAndHeater)

		if self._currentFile is not None:
			eventManager().fire(Events.PRINT_CANCELLED, {
				"file": self._currentFile["filename"],
				"filename": os.path.basename(self._currentFile["filename"]),
				"origin": FileDestinations.LOCAL,
			})

			self._fileManager.printFailed(self._currentFile["filename"], self.getPrintTime())
			payload = {
				"file": self._currentFile["filename"],
				"origin": FileDestinations.LOCAL
			}

			if 'sd' in self._currentFile and self._currentFile["sd"]:
				payload["origin"] = FileDestinations.SDCARD

			eventManager().fire(Events.PRINT_CANCELLED, payload)


	def printJobCancelled(self):
		# reset progress, height, print time
		self._setProgressData(None, None, None, None, None)

		# mark print as failure
		if self._currentFile is not None:
			self._fileManager.printFailed(self._currentFile["filename"], self.getPrintTime())
			self.unselectFile()
			self._currentFile = None

	def getCurrentConnection(self):
		port, baudrate = self._plugin.currentConnection
		return self.getStateString(), port, baudrate

	def jog(self, axis, amount):
		self._plugin.jog(axis, self.jogAmountWithPrinterProfile(axis, amount))

	def home(self, axes):
		self._plugin.home(axes)

	def fan(self, tool, speed):
		self._plugin.fan(tool, speed)

	def extrude(self, tool, amount, speed=None):
		self._plugin.extrude(tool, amount, speed)

	def changeTool(self, tool):
		self._plugin.changeTool(tool)

	def setTemperature(self, type, value):
		self._plugin.setTemperature(type, value)

	def sendRawCommand(self, command):
		self._plugin.sendCommand(command)

	def getShortErrorString(self):
		return "Virtual Error"

	def serialList(self):
		return self._plugin.ports

	def baudrateList(self):
		return self._plugin.baudRates

	def getStateString(self):
		return str(self._plugin.printerState)

	def getPrintProgress(self):
		return self._plugin.printProgress

	def getPrintFilepos(self):
		return self._plugin.printFilePosition

	def getConsumedFilament(self):
		return self._plugin.consumedFilamentData

	def getTotalConsumedFilament(self):
		return self._plugin.consumedFilamentSum

	def isOperational(self):
		return self._plugin.operational

	def isClosedOrError(self):
		return self._plugin.conectionClosedOrError

	def isError(self):
		return self._plugin.conectionError

	def isBusy(self):
		return  self._plugin.printing or self._plugin.paused

	def isPrinting(self):
		return self._plugin.printing

	def isPaused(self):
		return self._plugin.paused

	def setPause(self, paused):
		self._plugin.paused = paused

	def isReady(self):
		return self._plugin.connected and not self._plugin.printing

	def isStreaming(self):
		return self._plugin.streaming

	def isHeatingUp(self):
		return self._plugin.preHeating

	def isConnected(self):
		return self._plugin.connected

	def resetSerialLogging(self):
		self._plugin.serialLoggingChanged()

	def getCurrentTemperatures(self):
		return self._plugin.getCurrentTemperatures()

	def getSelectedTool(self):
		return 0

	# Plugin Manager Event Listener
	def onPluginRemoved(self, plugin):
		if plugin.pluginId == self._plugin.pluginId:
			# We just lost the active comms plugin so we'll pick the default one now
			from astroprint.printer.manager import DEFAULT_MANAGER

			self._profileManager.set({'driver': DEFAULT_MANAGER})
			self._profileManager.save()
