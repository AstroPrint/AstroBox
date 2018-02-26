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
from astroprint.cloud import astroprintCloud

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

	def getConnectionOptions(self):
		"""
		 Retrieves the available ports, baudrates, prefered port and baudrate for connecting to the printer.
		"""
		s = settings()

		return {
			"ports": self.serialList(),
			"baudrates": self.baudrateList(),
			"portPreference": s.get(["serial", "port"]),
			"baudratePreference": s.getInt(["serial", "baudrate"]),
			"autoconnect": s.getBoolean(["serial", "autoconnect"])
		}

	@property
	def allowTerminal(self):
		return self._plugin.allowTerminal

	@property
	def selectedFile(self):
		return self._currentFile

	@property
	def _fileManagerClass(self):
		return self._plugin.fileManagerClass

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

	def getFileInfo(self, filename):
		estimatedPrintTime = None
		date = None
		filament = None
		layerCount = None
		cloudId = None
		renderedImage = None
		printFileName = None

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

			if fileData is not None and "image" in fileData.keys():
				renderedImage = fileData["image"]

			cloudId = self._fileManager.getFileCloudId(filename)
			if cloudId:
				if self._selectedFile:
					self._selectedFile['cloudId'] = cloudId

				printFile = astroprintCloud().getPrintFile(cloudId)
				if printFile:
					renderedImage = printFile['images']['square']

			if fileData is not None and "printFileName" in fileData.keys():
				printFileName = fileData["printFileName"]

		return {
			"file": {
				"name": os.path.basename(filename) if filename is not None else None,
				"printFileName": printFileName,
				"origin": FileDestinations.LOCAL,
				"date": date,
				"cloudId": cloudId,
				"rendered_image": renderedImage
			},
			"estimatedPrintTime": estimatedPrintTime,
			"layerCount": layerCount,
			"filament": filament,
		}

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

			##self._fileManager.printFailed(self._currentFile["filename"], self.getPrintTime())
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

	def getSelectedTool(self):
		return self._plugin.currentTool


	# Plugin Manager Event Listener
	def onPluginRemoved(self, plugin):
		if plugin.pluginId == self._plugin.pluginId:
			# We just lost the active comms plugin so we'll pick the default one now
			from astroprint.printer.manager import DEFAULT_MANAGER

			self._profileManager.set({'driver': DEFAULT_MANAGER})
			self._profileManager.save()
