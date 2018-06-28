# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os

from octoprint.events import eventManager, Events as SystemEvent

from astroprint.plugin.providers.printer_comms.material_counter import MaterialCounter
from astroprint.plugin.providers.printer_comms.commands import CommandPluginInterface

class PrinterState():
	STATE_NONE = 0
	#STATE_DETECT_SERIAL = 2
	#STATE_DETECT_BAUDRATE = 3
	STATE_CONNECTING = 4
	STATE_OPERATIONAL = 5
	STATE_PRINTING = 6
	STATE_PAUSED = 7
	STATE_CLOSED = 8
	STATE_ERROR = 9
	STATE_CLOSED_WITH_ERROR = 10
	STATE_TRANSFERING_FILE = 11

	def __init__(self, value = 0):
		self._state = value

	def __str__(self):
		if self._state == self.STATE_NONE:
			return "Offline"
		#if self._state == self.STATE_DETECT_SERIAL:
		#	return "Detecting serial port"
		#if self._state == self.STATE_DETECT_BAUDRATE:
		#	return "Detecting baudrate"
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
			return "Error"
		if self._state == self.STATE_CLOSED_WITH_ERROR:
			return "Closed With Error"
		if self._state == self.STATE_TRANSFERING_FILE:
			return "Transfering file to SD"
		return "?%d?" % (self._state)

	def __eq__(self, value):
		return self._state == value

class PrinterCommsService(CommandPluginInterface):

	## Implement these functions ##

	#
	# Perform a connection to the printer.
	#
	# - port: The name of the port to use
	# - baudrate: The baudrate to use with the connection
	#
	def connect(self, port=None, baudrate=None):
		raise NotImplementedError()

	#
	# Perform a disconnection from the printer.
	#
	def disconnect(self, port=None, baudrate=None):
		raise NotImplementedError()

	#
	# Start a print job using the currently selected file
	#
	def startPrint(self):
		raise NotImplementedError()

	#
	# Sends the custom Cancel commands
	#
	# - disableMotorsAndHeater: whether we need to disable the stepper motors and the heaters
	#
	def executeCancelCommands(self, disableMotorsAndHeater):
		raise NotImplementedError()

	#
	# Send commands to the printer to disable heaters and motors
	#
	def disableMotorsAndHeater(self):
		raise NotImplementedError()

	#
	# Moves the print head in the axis specified by the specified mm
	#
	# - axis: 'x', 'y', 'z'
	#	- amount: distrance in milimeters
	#
	def jog(self, axis, amount):
		raise NotImplementedError()

	#
	# Home the specified axes
	#
	# - axes: Array containing one or more of 'x', 'y', 'z'
	#
	def home(self, axes):
		raise NotImplementedError()

	#
	# Change the fan speed for an extruder
	#
	# - tool: Number describing the extruder
	# - speed: Percentage speed to set (0-255)
	#
	def fan(self, tool, speed):
		raise NotImplementedError()

	#
	# Extruder filament from an extruder
	#
	# - tool: Number describing the extruder
	# - amount: amount in mm to extrude
	# - speed: speed to move at (mm/s)
	#
	def extrude(self, tool, amount, speed=None):
		raise NotImplementedError()

	#
	# Change the active extruder
	#
	# - tool: Number describing the extruder
	#
	def changeTool(self, tool):
		raise NotImplementedError()

	#
	# Sends a command to the printer
	#
	# - command: The command to sed
	#
	def sendCommand(self, command):
		raise NotImplementedError()

	#
	# Instruct the printer to set the temperature to the bed or nozzle
	#
	# - type: tool0, tool1 ... or bed
	# - value: The value in Celcius
	#
	def setTemperature(self, type, value):
		raise NotImplementedError()

	#
	# Pause/unpause the print jobs
	#
	# - paused: whether to pause (true) or resume (false) the print
	#
	def setPaused(self, paused):
		raise NotImplementedError()

	#
	# Called when the serial logging flag has changed, It should be re-checked to adjust to the new setting
	#
	def serialLoggingChanged(self):
		raise NotImplementedError()

	#
	# Returns an objects with the available ports to communicate with a connected printer.
	#
	# Return type: objedt
	#
	# - { portId: portName }
	#
	@property
	def ports(self):
		raise NotImplementedError()

	#
	# Returns a list of valid baud rates to connect to the printers:
	#
	# Return type: list of integers or None if device doesn't need baud rate
	#
	#
	@property
	def baudRates(self):
		raise NotImplementedError()

	#
	# Returns a tuple with the current connection settings.
	#
	#
	# Return type: tuple
	#
	# - (port, baudrate)
	#
	@property
	def currentConnection(self):
		raise NotImplementedError()

	#
	# Returns an object witht plugin properties to configure the settings view
	#
	# Return type: object
	#
	# - customCancelCommands: Whether the driver support custom GCODE to be send when canceling a print job
	#
	@property
	def settingsProperties(self):
		raise NotImplementedError()

	#
	# Returns the class that will interface with the files on the device
	#
	#
	# Return type: Class
	#
	@property
	def fileManagerClass(self):
		raise NotImplementedError()

	#
	# Returns whether a communication channel with the printer is active
	#
	#
	# Return type: boolean
	#
	@property
	def connected(self):
		raise NotImplementedError()

	#
	# Returns whether the printer is in the pre-heating phase before a print job
	#
	#
	# Return type: boolean
	#
	@property
	def preHeating(self):
		raise NotImplementedError()

	#
	# Returns the printing progress in percentage (1-100)
	#
	#
	# Return type: int
	#
	@property
	def printProgress(self):
		raise NotImplementedError()

	#
	# Returns the position of the current file being printed
	#
	#
	# Return type: int
	#
	@property
	def printFilePosition(self):
		raise NotImplementedError()

	## You can override these functions but make sure you call this parent ##

	#
	# Initializes the printer comms service. This is called when this plugin is selected as the active printer comms driver
	#
	# - printerManger: the printer manager instance that controls this plugin
	#
	def initPrinterCommsService(self, printerManager):
		self._printerState = PrinterState()
		self._materialCounter = MaterialCounter()
		self._printerManager = printerManager

		self._currentTool = 0
		self._printingSpeed = 100
		self._printingFlow = 100

		self._currentZ = 0
		self._lastLayerHeight = 0

	## Optionally implement these funcions if default behaviour is not enough ##

	#
	# Returns a boolean representing whether the printer allows the GCODE Terminal app
	#
	# Return type: boolean
	#
	@property
	def allowTerminal(self):
		return False

	#
	# Returns the printer state
	#
	# Return type: printer state
	#
	@property
	def printerState(self):
		return self._printerState

	@printerState.setter
	def printerState(self, state):
		self._printerState = state

	#
	# Returns the id of the currently selected extruder
	#
	@property
	def currentTool(self):
		return self._currentTool

	#
	# Returns a boolean representing whether the driver allows printing from the printer's SD Card
	#
	# Return type: boolean
	#
	@property
	def allowSDCardPrinting(self):
		return False

	#
	# Returns the printer is paused
	#
	# Return type: boolean
	#
	@property
	def paused(self):
		return self.printerState == PrinterState.STATE_PAUSED

	#
	# Returns whether the printer is currently printing
	#
	# Return type: boolean
	#
	@property
	def printing(self):
		return self.printerState == PrinterState.STATE_PRINTING

	#
	# Returns whether the printer is connected and without errors
	#
	# Return type: boolean
	#
	@property
	def operational(self):
		return self.connected and (self.printerState == PrinterState.STATE_OPERATIONAL or self.printerState == PrinterState.STATE_PRINTING or self.printerState == PrinterState.STATE_PAUSED)

	#
	# Returns whether the printer connection has suffered an error and it's no longer connected
	#
	# Return type: boolean
	#
	@property
	def conectionError(self):
		return self.printerState != PrinterState.STATE_CONNECTING and (not self.connected or self.printerState == PrinterState.STATE_ERROR or self.printerState == PrinterState.STATE_CLOSED_WITH_ERROR)

	#
	# Returns whether the printer connection has suffered an error or simply closed and it's no longer connected
	#
	# Return type: boolean
	#
	@property
	def conectionClosedOrError(self):
		return not self.connected or self.printerState == PrinterState.STATE_ERROR or self.printerState == PrinterState.STATE_CLOSED_WITH_ERROR or self.printerState == PrinterState.STATE_CLOSED

	#
	# Returns whether we're currently streaming a file to the printer
	#
	# Return type: boolean
	#
	@property
	def streaming(self):
		return False

	## Protected Functions that can be used by children ##

	def _changePrinterState(self, newState):
		if self.printerState == newState:
			return

		oldState = self.printerState
		self.printerState = PrinterState(newState)
		self._printerManager._state = newState
		self._logger.info('Changing printer state from [%s] to [%s]' % (oldState, self.printerState))

		# forward relevant state changes to gcode manager
		if self.connected and oldState == PrinterState.STATE_PRINTING:
			self._printerManager.fileManager.resumeAnalysis() # printing done, put those cpu cycles to good use
		elif self.connected and newState == PrinterState.STATE_PRINTING:
			self._printerManager.fileManager.pauseAnalysis() # do not analyze gcode while printing
		elif self.connected and newState == PrinterState.STATE_OPERATIONAL:
			eventManager().fire(SystemEvent.CONNECTED)
		elif newState == PrinterState.STATE_CONNECTING:
			eventManager().fire(SystemEvent.CONNECTING)
		elif newState == PrinterState.STATE_CLOSED or newState == PrinterState.STATE_ERROR:
			eventManager().fire(SystemEvent.DISCONNECTED)

		self._printerManager.refreshStateData()

	### Better to not override this functions

	#
	# Returns the position of the current file being printed
	#
	# Return type: object
	#
	@property
	def consumedFilamentData(self):
		return self._materialCounter.consumedFilament

	#
	# Returns the sum of all the filament consumed by all extruders
	#
	# Return type: object
	#
	@property
	def consumedFilamentSum(self):
		return self._materialCounter.totalConsumedFilament

	#
	# Pause/unpause the print jobs
	#
	# - paused: whether to pause (true) or resume (false) the print
	#
	@paused.setter
	def paused(self, paused):
		self.setPaused(paused)

	#
	# Report a temperature change
	#
	# - tools: It's an object with the following structure { tool_id<int>: (actual<int>, target<int>)}
	# - bed: It's a tuple with the following structure (actual<int>, target<int>)
	#
	def reportTempChange(self, tools, bed):
		self._printerManager.mcTempUpdate(tools, bed)

	#
	# Report print job completed
	#
	def reportPrintJobCompleted(self):
		self.disableMotorsAndHeater()

		currentFile = self._printerManager.selectedFile
		printTime = self._printerManager.getPrintTime()
		currentLayer = self._printerManager.getCurrentLayer()

		self._printerManager.mcPrintjobDone()

		self._changePrinterState(PrinterState.STATE_OPERATIONAL)

		self._printerManager._fileManager.printSucceeded(currentFile['filename'], printTime, currentLayer)
		eventManager().fire(SystemEvent.PRINT_DONE, {
			"file": currentFile['filename'],
			"filename": os.path.basename(currentFile['filename']),
			"origin": currentFile['origin'],
			"time": printTime,
			"layerCount": currentLayer
		})

	#
	# Report print job failed
	#
	def reportPrintJobFailed(self):
		currentFile = self._printerManager.selectedFile
		printTime = self._printerManager.getPrintTime()

		self._printerManager.printJobCancelled()

		filename = os.path.basename(currentFile['filename'])
		eventManager().fire(SystemEvent.PRINT_FAILED, {
			"file": currentFile['filename'],
			"filename": filename,
			"origin": currentFile['origin'],
			"time": printTime
		})
		##self._printerManager._fileManager.printFailed(filename, printTime)

	#
	# Call this function when print progress has changed
	#
	def reportPrintProgressChanged(self):
		self._printerManager.mcProgress()

	#
	# Call this function when there a layer change
	#
	def reportNewLayer(self):
		self._printerManager.reportNewLayer()

	#
	# Report a Heating Up change
	#
	# - heating: Whether the printer is heating up in preparation for a print job
	#
	def reportHeatingUpChange(self, heating):
		self._printerManager.mcHeatingUpUpdate(heating)

	#
	# Report a new active tool
	#
	# - newTool: The new tool that just got active
	# - oldTool: The previously selected tool
	#
	def reportToolChange(self, newTool, oldTool):
		self._printerManager.mcToolChange(newTool, oldTool)

	#
	# Report a new printing speed
	#
	# - amount: The printing speed in percentage
	#
	def reportPrintingSpeedChange(self, amount):
		self._printerManager.mcPrintingSpeedChange(amount)

	#
	# Report a new printing flow
	#
	# - amount: The printing flow in percentage
	#
	def reportPrintingFlowChange(self, amount):
		self._printerManager.mcPrintingFlowChange(amount)

	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# CommandPluginInterface     ~
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	@property
	def currentZ(self):
		return self._currentZ

	@property
	def lastLayerHeight(self):
		return self._lastLayerHeight

	def onWaitForTemperature(self):
		self.preHeating = True

	def onZMovement(self, z):
		if self._currentZ != z:
			self._currentZ = z

	def onExtrusionAfterZMovement(self):
		if self.printerState == PrinterState.STATE_PRINTING:
			if self._currentZ > self._lastLayerHeight:
				self.reportNewLayer()

			self._lastLayerHeight = self._currentZ

	def onExtrusionModeChanged(self, mode):
		self._materialCounter.changeExtrusionMode(mode)

	def onExtrusion(self, value):
		self._materialCounter.reportExtrusion(value)

	def onExtrusionLengthReset(self, value):
		# At the moment this command is only relevant in Absolute Extrusion Mode
		if self._materialCounter.extrusionMode == MaterialCounter.EXTRUSION_MODE_ABSOLUTE:
			self._materialCounter.resetExtruderLength(value)

	def onToolChanged(self, tool):
		if self._currentTool != tool:
			oldTool = self._currentTool

			self._materialCounter.changeActiveTool(str(tool), str(oldTool))
			self._currentTool = tool
			self.reportToolChange(tool, oldTool)

	def onPrintingSpeedChanged(self, amount):
		if self._printingSpeed != amount:
			self._printingSpeed = amount
			self.reportPrintingSpeedChange(amount)

	def onPrintingFlowChanged(self, amount):
		if self._printingFlow != amount:
			self._printingFlow = amount
			self.reportPrintingFlowChange(amount)
