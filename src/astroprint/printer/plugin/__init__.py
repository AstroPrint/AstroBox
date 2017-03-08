# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os

from octoprint.events import eventManager, Events

from astroprint.printer import Printer
from astroprint.plugin import pluginManager
from astroprint.printfiles import FileDestinations

class PrinterWithPlugin(Printer):
	driverName = 'plugin'

	def __init__(self, pluginId):
		self._plugin = pluginManager().getPlugin(pluginId)
		self._plugin.initPrinterCommsService(self)

		self._currentFile = None

		super(PrinterWithPlugin, self).__init__()

	@property
	def allowTerminal(self):
		return self._plugin.allowGCodeTerminal()

	@property
	def selectedFile(self):
		return self._currentFile

	@property
	def _fileManagerClass(self):
		return self._plugin.fileManagerClass()

	def connect(self, port=None, baudrate=None):
		return self._plugin.connect(port, baudrate)

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

	def printJobCancelled(self):
		# reset progress, height, print time
		self._setProgressData(None, None, None, None, None)

		# mark print as failure
		if self._currentFile is not None:
			self._fileManager.printFailed(self._currentFile["filename"], self.getPrintTime())
			self.unselectFile()

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
		self._plugin.sendComand(command)

	def getShortErrorString(self):
		return "Virtual Error"

	def serialList(self):
		return self._plugin.ports

	def baudrateList(self):
		return self._plugin.baudRates

	def getStateString(self):
		return str(self._plugin.printerState)

	def getPrintTime(self):
		return self._plugin.printTime

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
