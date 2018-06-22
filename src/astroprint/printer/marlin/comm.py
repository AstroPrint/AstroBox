# coding=utf-8

from __future__ import absolute_import

__author__ = "AstroPrint Product Team <product@astroprint.com> based on previous work by David Braam & Gina Häußge"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os
import time
import re
import threading
import logging
import serial

from collections import deque

from octoprint.settings import settings
from octoprint.events import eventManager, Events
from octoprint.util import getExceptionString, getNewTimeout, sanitizeAscii, filterNonAscii
from astroprint.util.gCodeAnalyzer import GCodeAnalyzer

from astroprint.printfiles import FileDestinations

from astroprint.plugin.providers.printer_comms.material_counter import MaterialCounter
from astroprint.printer.manager import printerManager

gcodeToEvent = {
	# pause for user input
	"M226": Events.WAITING,
	"M0": Events.WAITING,
	"M1": Events.WAITING,

	# part cooler
	"M245": Events.COOLING,

	# part conveyor
	"M240": Events.CONVEYOR,

	# part ejector
	"M40": Events.EJECT,

	# user alert
	"M300": Events.ALERT,

	# home print head
	"G28": Events.HOME,

	# emergency stop
	"M112": Events.E_STOP,

	# motors on/off
	"M80": Events.POWER_ON,
	"M81": Events.POWER_OFF,
}

class MachineCom(object):
	STATE_NONE = 0
	#STATE_OPEN_SERIAL = 1
	#STATE_DETECT_SERIAL = 2
	#STATE_DETECT_BAUDRATE = 3
	STATE_CONNECTING = 4
	STATE_OPERATIONAL = 5
	STATE_PRINTING = 6
	STATE_PAUSED = 7
	STATE_CLOSED = 8
	STATE_ERROR = 9
	STATE_CLOSED_WITH_ERROR = 10
	#STATE_TRANSFERING_FILE = 11

	def __init__(self, port = None, baudrate = None, callbackObject = None):
		self._logger = logging.getLogger(__name__)
		self._serialLogger = logging.getLogger("SERIAL")
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)
		self._settings = settings()

		if callbackObject == None:
			callbackObject = MachineComPrintCallback()

		self._port = port
		self._baudrate = baudrate
		self._callback = callbackObject
		self._state = self.STATE_NONE
		self._serial = None
		self._baudrateDetectList = callbackObject.baudrateList()
		self._baudrateDetectRetry = 0
		self._temp = {}
		self._bedTemp = None
		self._heatingUp = None
		self._commandQueue = deque()
		self._currentZ = None
		self._currentLayer = None
		self._lastLayerHeight = None
		self._heatupWaitStartTime = 0
		self._heatupWaitTimeLost = 0.0
		self._currentTool = 0
		self._printingSpeed = 100
		self._printingFlow = 100
		self._previousSelectedTool = 0
		self._oksAfterHeatingUp = 0
		self._pauseInProgress = False
		self._cancelInProgress = False

		#self._alwaysSendChecksum = self._settings.getBoolean(["feature", "alwaysSendChecksum"])
		self._currentLine = 1
		self._resendDelta = None
		self._lastLines = deque([], 100)

		# SD status data
		self._sdAvailable = False
		self._sdFileList = False
		self._sdFiles = []

		# print job
		self._currentFile = None
		self._positionWhenPaused = {}

		# regexes
		floatPattern = "[-+]?[0-9]*\.?[0-9]+"
		positiveFloatPattern = "[+]?[0-9]*\.?[0-9]+"
		intPattern = "\d+"
		self._regex_command = re.compile("^\s*([GM]\d+|T)")
		self._regex_float = re.compile(floatPattern)
		self._regex_paramZFloat = re.compile("Z(%s)" % floatPattern)
		self._regex_paramEFloat = re.compile("E(%s)" % floatPattern)
		self._regex_paramSInt = re.compile("S(%s)" % intPattern)
		self._regex_paramNInt = re.compile("N(%s)" % intPattern)
		self._regex_paramTInt = re.compile("T(%s)" % intPattern)
		self._regex_extrusion = re.compile("E%s" % positiveFloatPattern)
		self._regex_extruder = re.compile("E:(%s)" % positiveFloatPattern)
		self._regex_minMaxError = re.compile("Error:[0-9]\n")
		#self._regex_sdPrintingByte = re.compile("([0-9]*)/([0-9]*)")
		#self._regex_sdFileOpened = re.compile("File opened:\s*(.*?)\s+Size:\s*(%s)" % intPattern)
		self._regex_M114Response = re.compile("X:(%s)\s?Y:(%s)\s?Z:(%s)\s?E:(%s)" % (floatPattern, floatPattern, floatPattern, floatPattern))

		# Regex matching temperature entries in line. Groups will be as follows:
		# - 1: whole tool designator incl. optional toolNumber ("T", "Tn", "B")
		# - 2: toolNumber, if given ("", "n", "")
		# - 3: actual temperature
		# - 4: whole target substring, if given (e.g. " / 22.0")
		# - 5: target temperature
		self._regex_temp = re.compile("(B|T(\d*)):\s*(%s)(\s*\/?\s*(%s))?" % (positiveFloatPattern, positiveFloatPattern))
		self._regex_repetierTempExtr = re.compile("TargetExtr([0-9]+):(%s)" % positiveFloatPattern)
		self._regex_repetierTempBed = re.compile("TargetBed:(%s)" % positiveFloatPattern)

		# multithreading locks as these functions can be called from different threads
		self._sendingLock = threading.Lock()
		self._newLineNumberLock = threading.Lock()

		self.timerCalculator = None
		self.timePerLayers =  None
		self.totalPrintTime = None
		self.layerCount = None
		self.size = None
		self.layer_height = None
		self.total_filament = None

		#Material Counter
		self._materialCounter = MaterialCounter()

		# monitoring thread
		self.thread = threading.Thread(target=self._monitor)
		self.thread.daemon = True
		self.thread.start()

	def __del__(self):
		self._logger.debug('Printer Comm removed')
		self.close()

	def resetSerialLogging(self):
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)

	##~~ internal state management

	def _changeState(self, newState):
		if self._state == newState:
			return

		# if newState == self.STATE_CLOSED or newState == self.STATE_CLOSED_WITH_ERROR:
		# 	if self._settings.get(["feature", "sdSupport"]):
		# 		self._sdFileList = False
		# 		self._sdFiles = []
		# 		self._callback.mcSdFiles([])

		oldState = self.getStateString()
		self._state = newState
		self._logger.info('Changing printer state from [%s] to [%s]' % (oldState, self.getStateString()))

		if newState == self.STATE_ERROR:
			# we need to issue the event here becaus the error message is in this class
			# in case of error mcStateChange will close the comm object
			eventManager().fire(Events.ERROR, {"error": self.getErrorString()})

		self._callback.mcStateChange(newState)

	def _log(self, message):
		#Currently we don't want the logs to clogg the notification between box/boxrouter/browser
		#self._callback.mcLog(message)
		self._serialLogger.debug(message)

	def _addToLastLines(self, cmd):
		self._lastLines.append(cmd)
		self._logger.debug("Got %d lines of history in memory" % len(self._lastLines))

	##~~ getters

	def getState(self):
		return self._state

	def getStateString(self):
		if self._state == self.STATE_NONE:
			return "Offline"
		#if self._state == self.STATE_OPEN_SERIAL:
		#	return "Opening serial port"
		#if self._state == self.STATE_DETECT_SERIAL:
		#	return "Detecting serial port"
		#if self._state == self.STATE_DETECT_BAUDRATE:
		#	return "Detecting baudrate"
		if self._state == self.STATE_CONNECTING:
			return "Connecting"
		if self._state == self.STATE_OPERATIONAL:
			return "Operational"
		if self._state == self.STATE_PRINTING:
			if self.isSdFileSelected():
				return "Printing from SD"
			elif self.isStreaming():
				return "Sending file to SD"
			else:
				return "Printing"
		if self._state == self.STATE_PAUSED:
			return "Paused"
		if self._state == self.STATE_CLOSED:
			return "Closed"
		if self._state == self.STATE_ERROR:
			return "Error: %s" % (self.getShortErrorString())
		if self._state == self.STATE_CLOSED_WITH_ERROR:
			return "Closed with Error: %s" % (self.getShortErrorString())
		#if self._state == self.STATE_TRANSFERING_FILE:
		#	return "Transfering file to SD"
		return "?%d?" % (self._state)

	def getShortErrorString(self):
		if len(self._errorValue) < 50:
			return self._errorValue
		return self._errorValue[:50] + "..."

	def getErrorString(self):
		return self._errorValue

	def isClosedOrError(self):
		return self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR or self._state == self.STATE_CLOSED

	def isError(self):
		return self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR

	def isOperational(self):
		return self._state == self.STATE_OPERATIONAL or self._state == self.STATE_PRINTING or self._state == self.STATE_PAUSED #or self._state == self.STATE_TRANSFERING_FILE

	def isPrinting(self):
		return self._state == self.STATE_PRINTING and not self._cancelInProgress

	def isSdPrinting(self):
		return self.isSdFileSelected() and self.isPrinting()

	def isSdFileSelected(self):
		return self._currentFile is not None and isinstance(self._currentFile, PrintingSdFileInformation)

	def isStreaming(self):
		return self._currentFile is not None and isinstance(self._currentFile, StreamingGcodeFileInformation)

	def isPaused(self):
		return self._state == self.STATE_PAUSED or self._pauseInProgress

	def isBusy(self):
		return self.isPrinting() or self.isPaused()

	def isSdReady(self):
		return self._sdAvailable

	def isHeatingUp(self):
		return self._heatingUp

	def getPrintProgress(self):
		if self._currentFile is None:
			return None
		return self._currentFile.getProgress()

	def getPrintFilepos(self):
		if self._currentFile is None:
			return None
		return self._currentFile.getFilepos()

	def getPrintTime(self):
		if self._currentFile is None or self._currentFile.getStartTime() is None:
			return None
		else:
			return time.time() - self._currentFile.getStartTime()

	def getTemp(self):
		return self._temp

	def getBedTemp(self):
		return self._bedTemp

	def getConnection(self):
		return self._port, self._baudrate

	def getConsumedFilament(self):
		return self._materialCounter.consumedFilament

	def getTotalConsumedFilament(self):
		return self._materialCounter.totalConsumedFilament

	def getSelectedTool(self):
		return self._currentTool

	def getPrintingSpeed(self):
		return self._printingSpeed

	def getPrintingFlow(self):
		return self._printingFlow

	##~~ external interface

	def close(self, isError = False):
		if self._serial is not None:
			try:
				self._serial.close()
			except OSError as e:
				#log it but continue
				self._logger.error('Error closing serial port: %s' % e)

			if isError:
				self._changeState(self.STATE_CLOSED_WITH_ERROR)
			else:
				self._changeState(self.STATE_CLOSED)

		self._serial = None

		# if self._settings.get(["feature", "sdSupport"]):
		# 	self._sdFileList = []

		if self.isPrinting() or self.isPaused():
			payload = None
			if self._currentFile is not None:
				payload = {
					"file": self._currentFile.getFilename(),
					"filename": os.path.basename(self._currentFile.getFilename()),
					"origin": self._currentFile.getFileLocation()
				}
			eventManager().fire(Events.PRINT_FAILED, payload)

		eventManager().fire(Events.DISCONNECTED)

	def sendCommand(self, cmd):
		cmd = cmd.encode('ascii', 'replace')
		if self.isPrinting() or self._pauseInProgress:
			self._commandQueue.appendleft(cmd)
		elif self.isOperational():
			self._sendCommand(cmd)

	def startPrint(self):
		if not self.isOperational() or self.isPrinting():
			return

		if self._currentFile is None:
			raise ValueError("No file selected for printing")

		self._materialCounter.startPrint()

		try:
			self._currentFile.start()
			self._lastLayerHeight = 0.0
			self._currentLayer  = 0
			self._oksAfterHeatingUp = 3
			self._pauseInProgress = False
			self.__pauseInProgress = False
			#self._currentLayer = 1
			#sefl._lastLayerHeight
			#self._callback.mcLayerChange(self._tentativeLayer)

			self._changeState(self.STATE_PRINTING)

			data = printerManager().getFileInfo(self._currentFile.getFilename())
			eventManager().fire(Events.PRINT_STARTED, data)

			# if self.isSdFileSelected():
			# 	if wasPaused:
			# 		self.sendCommand("M26 S0")
			# 		self._currentFile.setFilepos(0)
			# 	self.sendCommand("M24")
			# else:

			#reset line counter
			self._sendCommand("M110 N0")

			#clear the command queue so that it's empty for the print
			self._commandQueue.clear()

			#start sending gcode from file
			firstCmd = self._getNextFileCommand()
			if firstCmd:
				self._commandQueue.appendleft(firstCmd)

		except:
			self._errorValue = getExceptionString()
			self._changeState(self.STATE_ERROR)

	def startFileTransfer(self, filename, localFilename, remoteFilename):
		if not self.isOperational() or self.isBusy():
			logging.info("Printer is not operation or busy")
			return

		self._currentFile = StreamingGcodeFileInformation(filename, localFilename, remoteFilename)
		self._currentFile.start()

		self.sendCommand("M28 %s" % remoteFilename)
		eventManager().fire(Events.TRANSFER_STARTED, {"local": localFilename, "remote": remoteFilename})
		self._callback.mcFileTransferStarted(remoteFilename, self._currentFile.getFilesize())

	def selectFile(self, filename, sd):
		if self.isBusy():
			return False

		if sd:
			if not self.isOperational():
				# printer is not connected, can't use SD
				return False
			self.sendCommand("M23 %s" % filename)
		else:
			self._currentFile = PrintingGcodeFileInformation(filename)

		return True

	def unselectFile(self):
		if self.isBusy():
			return False

		self._currentFile = None
		return True

	def cancelPrint(self):
		if not self.isOperational():# or self.isStreaming():
			return

		#if self.isSdFileSelected():
		#	self.sendCommand("M25")    # pause print
		#	self.sendCommand("M26 S0") # reset position in file to byte 0

		self.unselectFile()
		self._changeState(self.STATE_OPERATIONAL)
		self._heatingUp = False
		self._callback.mcHeatingUpUpdate(self._heatingUp)
		self._cancelInProgress = False
		self._pauseInProgress = False

	def setPause(self, pause):
		#if self.isStreaming():
		#	return

		if not pause and self.isPaused():
			#if self.isSdFileSelected():
			#	self.sendCommand("M24")
			#else:

			if (self._previousSelectedTool != self._currentTool):
				self.sendCommand("T%d" % self._previousSelectedTool)

			self._pauseInProgress = False
			self._changeState(self.STATE_PRINTING)

			#restore position

			if self._positionWhenPaused:
				self._currentZ = self._positionWhenPaused[2] # To avoid miscounting layers
				#We need to lift the Z axis first in case they lowered it
				self._commandQueue.appendleft("G1 Z%.4f F2000" % ( self._positionWhenPaused[2] + 10 ))
				#Get back to where you were before pausing
				self._commandQueue.appendleft("G1 X%.4f Y%.4f F9000" % (self._positionWhenPaused[0], self._positionWhenPaused[1] ))
				#Position the actual Z height
				self._commandQueue.appendleft("G1 Z%.4f F2000" % ( self._positionWhenPaused[2] ))
				#slow down the speed for the first movement
				self._commandQueue.appendleft("G1 F1000")
				#reset extrusion to what it was in case we did some extrusion while paused minus the retract
				self._commandQueue.appendleft("G92 E%.4f" % (self._positionWhenPaused[3] - 5))

				#send the first enqueued command, this will in turn resume file reading when queue is empty
				self._sendCommand(self._commandQueue.pop(), True)
			else:
				self._logger.warn('There was no stored position on resume command')
				self._sendNextFileCommand()

			eventManager().fire(Events.PRINT_RESUMED, {
				"file": self._currentFile.getFilename(),
				"filename": os.path.basename(self._currentFile.getFilename()),
				"origin": self._currentFile.getFileLocation()
			})

		elif pause and self.isPrinting():
			#if self.isSdFileSelected():
			#	self.sendCommand("M25") # pause print
			#else:

			self._pauseInProgress = True
			self.sendCommand("M110 N0")
			self.sendCommand("M106 S0") #Stop fans
			self.sendCommand("M114") # Current position is saved at self._positionWhenPaused
			#the head movement out of the way and adding the _apCommand_PAUSE to the queue is done on the M114 response when self._pauseInProgress is True

			eventManager().fire(Events.PRINT_PAUSED, {
				"file": self._currentFile.getFilename(),
				"filename": os.path.basename(self._currentFile.getFilename()),
				"origin": self._currentFile.getFileLocation()
			})

			self._previousSelectedTool = self.getSelectedTool()
			self._changeState(self.STATE_PAUSED)

	def getSdFiles(self):
		pass
		#return self._sdFiles

	def startSdFileTransfer(self, filename):
		pass
		# if not self.isOperational() or self.isBusy():
		# 	return

		# self._changeState(self.STATE_TRANSFERING_FILE)
		# self.sendCommand("M28 %s" % filename.lower())

	def endSdFileTransfer(self, filename):
		pass
		# if not self.isOperational() or self.isBusy():
		# 	return

		# self.sendCommand("M29 %s" % filename.lower())
		# self._changeState(self.STATE_OPERATIONAL)
		# self.refreshSdFiles()

	def deleteSdFile(self, filename):
		pass
		# if not self.isOperational() or (self.isBusy() and
		# 		isinstance(self._currentFile, PrintingSdFileInformation) and
		# 		self._currentFile.getFilename() == filename):
		# 	# do not delete a file from sd we are currently printing from
		# 	return

		# self.sendCommand("M30 %s" % filename.lower())
		# self.refreshSdFiles()

	def refreshSdFiles(self):
		pass
		# if not self.isOperational() or self.isBusy():
		# 	return
		# self.sendCommand("M20")
		# we currently don't do anything with SD cards so avoid this for now

	def initSdCard(self):
		# we currently don't do anything with SD cards so avoid this for now
		pass

		# if not self.isOperational():
		# 	return
		# self.sendCommand("M21")
		# if self._settings.getBoolean(["feature", "sdAlwaysAvailable"]):
		# 	self._sdAvailable = True
		# 	self.refreshSdFiles()
		# 	self._callback.mcSdStateChange(self._sdAvailable)

	def releaseSdCard(self):
		pass
		# if not self.isOperational() or (self.isBusy() and self.isSdFileSelected()):
		# 	# do not release the sd card if we are currently printing from it
		# 	return

		# self.sendCommand("M22")
		# self._sdAvailable = False
		# self._sdFiles = []

		# self._callback.mcSdStateChange(self._sdAvailable)
		# self._callback.mcSdFiles(self._sdFiles)

	##~~ communication monitoring and handling

	def _parseTemperatures(self, line):
		result = {}
		maxToolNum = 0
		for match in re.finditer(self._regex_temp, line):
			tool = match.group(1)
			toolNumber = int(match.group(2)) if match.group(2) and len(match.group(2)) > 0 else None
			if toolNumber > maxToolNum:
				maxToolNum = toolNumber

			try:
				actual = float(match.group(3))
				target = None
				if match.group(4) and match.group(5):
					target = float(match.group(5))

				result[tool] = (toolNumber, actual, target)
			except ValueError:
				# catch conversion issues, we'll rather just not get the temperature update instead of killing the connection
				pass

		if "T0" in result.keys() and "T" in result.keys():
			del result["T"]

		return maxToolNum, result

	def _parseExtruder(self, line):
		extruder = 0
		extruderMatch = 'E:'

		for match in re.finditer(self._regex_extruder, line):
			extruder = match.group(1)
			extruderMatch = match.group(0)

		return  extruderMatch, extruder


	def _processTemperatures(self, line):
		maxToolNum, parsedTemps = self._parseTemperatures(line)
		extruderMatch, extruder = self._parseExtruder(line)

		# extruder temperatures
		if not "T0" in parsedTemps.keys() and "T" in parsedTemps.keys():
			toolNum, actual, target = parsedTemps["T"]

			if not extruderMatch in line:
				# only single reporting, "T" is our one and only extruder temperature
				if target is not None:
					self._temp[0] = (actual, target)
				elif 0 in self._temp.keys() and self._temp[0] is not None and isinstance(self._temp[0], tuple):
					oldActual, oldTarget = self._temp[0]
					self._temp[0] = (actual, oldTarget)
				else:
					self._temp[0] = (actual, None)
			else:
				# check when the printer send only a current extruder temperature but the printer have multiple extruders
				toolNum = int(extruder)

				if toolNum in self._temp.keys() and self._temp[toolNum] is not None and isinstance(self._temp[toolNum], tuple):
					(oldActual, oldTarget) = self._temp[toolNum]
					self._temp[toolNum] = (actual, oldTarget)
				else:
					self._temp[toolNum] = (actual, None)

		elif "T0" in parsedTemps.keys():
			for n in range(maxToolNum + 1):
				tool = "T%d" % n
				if not tool in parsedTemps.keys():
					continue

				toolNum, actual, target = parsedTemps[tool]
				if target is not None:
					self._temp[toolNum] = (actual, target)
				elif toolNum in self._temp.keys() and self._temp[toolNum] is not None and isinstance(self._temp[toolNum], tuple):
					(oldActual, oldTarget) = self._temp[toolNum]
					self._temp[toolNum] = (actual, oldTarget)
				else:
					self._temp[toolNum] = (actual, None)

		# bed temperature
		if "B" in parsedTemps.keys():
			toolNum, actual, target = parsedTemps["B"]
			if target is not None:
				self._bedTemp = (actual, target)
			elif self._bedTemp is not None and isinstance(self._bedTemp, tuple):
				(oldActual, oldTarget) = self._bedTemp
				self._bedTemp = (actual, oldTarget)
			else:
				self._bedTemp = (actual, None)

	def cleanPrintingVars(self):
		self.timePerLayers =  None
		self.totalPrintTime = None
		self.layerCount = None
		self.size = None
		self.layer_height = None
		self.total_filament = None
		self.timerCalculator = None

	def cbGCodeAnalyzerReady(self,timePerLayers,totalPrintTime,layerCount,size,layer_height,total_filament,parent):

		self.timePerLayers =  timePerLayers

		if not self.totalPrintTime:
			self.totalPrintTime = totalPrintTime*1.07

		self.layerCount = layerCount

		self.size = size

		self.layer_height = layer_height

		self.total_filament = None#total_filament has not got any information

	def _monitor(self):
		#Open the serial port.
		self._changeState(self.STATE_CONNECTING)

		if not self._openSerial():
			return

		self._serialLoggerEnabled and self._log("Connected to: %s, starting monitor" % self._serial)

		#Start monitoring the serial port.
		timeout = getNewTimeout("communication")
		tempRequestTimeout = getNewTimeout("temperature")
		#sdStatusRequestTimeout = getNewTimeout("sdStatus")
		self._heatingUp = False
		supportRepetierTargetTemp = self._settings.getBoolean(["feature", "repetierTargetTemp"])

		if self._state == self.STATE_CONNECTING:
			self._sendCommand("M105")

		while True:
			try:
				line = self._readline()
				if line is None:
					break
				if line.strip() is not "" and line.isalnum():
					timeout = getNewTimeout("communication")

				##~~ Error handling
				line, lineLower = self._lowerAndHandleErrors(line)

				##~~ SD file list
				# if we are currently receiving an sd file list, each line is just a filename, so just read it and abort processing
				# if self._sdFileList and not "End file list" in line:
				# 	fileinfo = line.strip().split(None, 2)
				# 	if len(fileinfo) > 1:
				# 		# we got extended file information here, so let's split filename and size and try to make them a bit nicer
				# 		filename, size = fileinfo
				# 		filename = filename.lower()
				# 		try:
				# 			size = int(size)
				# 		except ValueError:
				# 			# whatever that was, it was not an integer, so we'll just ignore it and set size to None
				# 			size = None
				# 	else:
				# 		# no extended file information, so only the filename is there and we set size to None
				# 		filename = fileinfo[0].lower()
				# 		size = None

				# 	if self._callback.fileManager.isValidFilename(filename):
				# 		if filterNonAscii(filename):
				# 			self._logger.warn("Got a file from printer's SD that has a non-ascii filename (%s), that shouldn't happen according to the protocol" % filename)
				# 		else:
				# 			self._sdFiles.append((filename, size))
				# 		continue

				##~~ Temperature processing
				if ' T:' in line or line.startswith('T:'):
					self._processTemperatures(line)
					self._callback.mcTempUpdate(self._temp, self._bedTemp)

					#If we are waiting for an M109 or M190 then measure the time we lost during heatup, so we can remove that time from our printing time estimate.
					if not 'ok' in lineLower and self._heatupWaitStartTime != 0:
						t = time.time()
						self._heatupWaitTimeLost = t - self._heatupWaitStartTime
						self._heatupWaitStartTime = t
				elif supportRepetierTargetTemp and ('TargetExtr' in line or 'TargetBed' in line):
					matchExtr = self._regex_repetierTempExtr.match(line)
					matchBed = self._regex_repetierTempBed.match(line)

					if matchExtr is not None:
						toolNum = int(matchExtr.group(1))
						try:
							target = float(matchExtr.group(2))
							if toolNum in self._temp.keys() and self._temp[toolNum] is not None and isinstance(self._temp[toolNum], tuple):
								actual, oldTarget = self._temp[toolNum]
								self._temp[toolNum] = (actual, target)
							else:
								self._temp[toolNum] = (None, target)
							self._callback.mcTempUpdate(self._temp, self._bedTemp)
						except ValueError:
							pass
					elif matchBed is not None:
						try:
							target = float(matchBed.group(1))
							if self._bedTemp is not None and isinstance(self._bedTemp, tuple):
								(actual, oldTarget) = self._bedTemp
								self._bedTemp = (actual, target)
							else:
								self._bedTemp = (None, target)
							self._callback.mcTempUpdate(self._temp, self._bedTemp)
						except ValueError:
							pass

				##~~ SD Card handling
				# elif 'SD init fail' in line or 'volume.init failed' in line or 'openRoot failed' in line:
				# 	self._sdAvailable = False
				# 	self._sdFiles = []
				# 	self._callback.mcSdStateChange(self._sdAvailable)
				# elif 'Not SD printing' in line:
				# 	if self.isSdFileSelected() and self.isPrinting():
				# 		# something went wrong, printer is reporting that we actually are not printing right now...
				# 		self._sdFilePos = 0
				# 		self._changeState(self.STATE_OPERATIONAL)
				# elif 'SD card ok' in line and not self._sdAvailable:
				# 	self._sdAvailable = True
				# 	self.refreshSdFiles()
				# 	self._callback.mcSdStateChange(self._sdAvailable)
				# elif 'Begin file list' in line:
				# 	self._sdFiles = []
				# 	self._sdFileList = True
				# elif 'End file list' in line:
				# 	self._sdFileList = False
				# 	self._callback.mcSdFiles(self._sdFiles)
				# elif 'SD printing byte' in line:
				# 	# answer to M27, at least on Marlin, Repetier and Sprinter: "SD printing byte %d/%d"
				# 	match = self._regex_sdPrintingByte.search(line)
				# 	self._currentFile.setFilepos(int(match.group(1)))
				# 	self._callback.mcProgress()
				# elif 'File opened' in line:
				# 	# answer to M23, at least on Marlin, Repetier and Sprinter: "File opened:%s Size:%d"
				# 	match = self._regex_sdFileOpened.search(line)
				# 	self._currentFile = PrintingSdFileInformation(match.group(1), int(match.group(2)))
				# elif 'File selected' in line:
				# 	# final answer to M23, at least on Marlin, Repetier and Sprinter: "File selected"
				# 	if self._currentFile is not None:
				# 		self._callback.mcFileSelected(self._currentFile.getFilename(), self._currentFile.getFilesize(), True)
				# 		eventManager().fire(Events.FILE_SELECTED, {
				# 			"file": self._currentFile.getFilename(),
				# 			"origin": self._currentFile.getFileLocation()
				# 		})
				# elif 'Writing to file' in line:
				# 	# anwer to M28, at least on Marlin, Repetier and Sprinter: "Writing to file: %s"
				# 	self._printSection = "CUSTOM"
				# 	self._changeState(self.STATE_PRINTING)
				# 	line = "ok"
				# elif 'Done printing file' in line:
				# 	# printer is reporting file finished printing
				# 	self._sdFilePos = 0
				# 	self._callback.mcPrintjobDone()
				# 	self._changeState(self.STATE_OPERATIONAL)
				# 	eventManager().fire(Events.PRINT_DONE, {
				# 		"file": self._currentFile.getFilename(),
				# 		"filename": os.path.basename(self._currentFile.getFilename()),
				# 		"origin": self._currentFile.getFileLocation(),
				# 		"time": self.getPrintTime(),
				# 		"layerCount": self._currentLayer
				# 	})
				# elif 'Done saving file' in line:
				# 	self.refreshSdFiles()

				##~~ Message handling
				#elif line.strip() != '' \
				#		and line.strip() != 'ok' and not line.startswith("wait") \
				#		and not line.startswith('Resend:') \
				#		and line != 'echo:Unknown command:""\n' \
				#		and self.isOperational():
				#	self._callback.mcMessage(line)

				##~~ Parsing for feedback commands
				# if feedbackControls:
				# 	for name, matcher, template in feedbackControls:
				# 		if name in feedbackErrors:
				# 			# we previously had an error with that one, so we'll skip it now
				# 			continue
				# 		try:
				# 			match = matcher.search(line)
				# 			if match is not None:
				# 				formatFunction = None
				# 				if isinstance(template, str):
				# 					formatFunction = str.format
				# 				elif isinstance(template, unicode):
				# 					formatFunction = unicode.format

				# 				if formatFunction is not None:
				# 					self._callback.mcReceivedRegisteredMessage(name, formatFunction(template, *(match.groups("n/a"))))
				# 		except:
				# 			if not name in feedbackErrors:
				# 				self._logger.info("Something went wrong with feedbackControl \"%s\": " % name, exc_info=True)
				# 				feedbackErrors.append(name)
				# 			pass

				##~~ Parsing for pause triggers
				# if pauseTriggers and not self.isStreaming():
				# 	if "enable" in pauseTriggers.keys() and pauseTriggers["enable"].search(line) is not None:
				# 		self.setPause(True)
				# 	elif "disable" in pauseTriggers.keys() and pauseTriggers["disable"].search(line) is not None:
				# 		self.setPause(False)
				# 	elif "toggle" in pauseTriggers.keys() and pauseTriggers["toggle"].search(line) is not None:
				# 		self.setPause(not self.isPaused())

				if self._heatingUp and "ok" in lineLower:
					if self._oksAfterHeatingUp == 0:
						self._heatingUp = False
						self._callback.mcHeatingUpUpdate(self._heatingUp)

						#self._currentFile.resetLayerPrintTime()
						##HEATED
					else:
						#HEATING
						self._oksAfterHeatingUp -= 1

						if not self.timerCalculator and self._currentFile: # It's possible that we just cancelled the print
							self.timerCalculator = GCodeAnalyzer(self._currentFile._filename,True,self.cbGCodeAnalyzerReady,None,self)
							self.timerCalculator.makeCalcs()

				### Baudrate detection
				# if self._state == self.STATE_DETECT_BAUDRATE:
				# 	if line == '' or time.time() > timeout:
				# 		if len(self._baudrateDetectList) < 1:
				# 			self.close()
				# 			self._errorValue = "No more baudrates to test, and no suitable baudrate found."
				# 			self._changeState(self.STATE_ERROR)
				# 			eventManager().fire(Events.ERROR, {"error": self.getErrorString()})
				# 		elif self._baudrateDetectRetry > 0:
				# 			self._baudrateDetectRetry -= 1
				# 			self._serial.write('\n')
				# 			self._serialLoggerEnabled and self._log("Baudrate test retry: %d" % (self._baudrateDetectRetry))
				# 			self._sendCommand("M105")
				# 			self._testingBaudrate = True
				# 		else:
				# 			baudrate = self._baudrateDetectList.pop(0)
				# 			try:
				# 				self._serial.baudrate = baudrate
				# 				self._serial.timeout = self._settings.getFloat(["serial", "timeout", "detection"])
				# 				self._serialLoggerEnabled and self._log("Trying baudrate: %d" % (baudrate))
				# 				self._baudrateDetectRetry = 5
				# 				self._baudrateDetectTestOk = 0
				# 				timeout = getNewTimeout("communication")
				# 				self._serial.write('\n')
				# 				self._sendCommand("M105")
				# 				self._testingBaudrate = True
				# 			except:
				# 				self._serialLoggerEnabled and self._log("Unexpected error while setting baudrate: %d %s" % (baudrate, getExceptionString()))
				# 	elif 'ok' in lineLower and 'T:' in line:
				# 		self._baudrateDetectTestOk += 1
				# 		if self._baudrateDetectTestOk < 10:
				# 			self._serialLoggerEnabled and self._log("Baudrate test ok: %d" % (self._baudrateDetectTestOk))
				# 			self._sendCommand("M105")
				# 		else:
				# 			self._sendCommand("M999")
				# 			self._serial.timeout = self._settings.getFloat(["serial", "timeout", "connection"])
				# 			self._changeState(self.STATE_OPERATIONAL)
				# 			# if self._sdAvailable:
				# 			# 	self.refreshSdFiles()
				# 			# else:
				# 			# 	self.initSdCard()
				# 			eventManager().fire(Events.CONNECTED, {"port": self._port, "baudrate": self._baudrate})
				# 	else:
				# 		self._testingBaudrate = False

				### Connection attempt
				if self._state == self.STATE_CONNECTING:
					if line == "" or "wait" in lineLower:
						self._sendCommand("M105")

					elif "ok" in lineLower:
						self._changeState(self.STATE_OPERATIONAL)
						# if self._sdAvailable:
						# 	self.refreshSdFiles()
						# else:
						# 	self.initSdCard()
						eventManager().fire(Events.CONNECTED, {"port": self._port, "baudrate": self._baudrate})

					elif "echo" in lineLower or "start" in lineLower:
						timeout = getNewTimeout("communication")

					elif time.time() > timeout:
						self._logger.warn('Printer did not respond in time')
						self.close()

				### Operational
				elif self._state == self.STATE_OPERATIONAL or self._state == self.STATE_PAUSED:
					#Request the temperature on comm timeout (every 5 seconds) when we are not printing.
					if line == "" or "wait" in lineLower or "ok" in lineLower:
						if self._resendDelta is not None:
							self._resendNextCommand()
						elif len(self._commandQueue) > 0:
							self._sendCommand(self._commandQueue.pop())
						elif self._callback.doIdleTempReports and time.time() > tempRequestTimeout:
							self.sendCommand("M105")
							tempRequestTimeout = getNewTimeout("temperature")
					# resend -> start resend procedure from requested line
					elif line.lower().startswith("resend") or line.lower().startswith("rs"):
						self._handleResendRequest(line)

					elif self._pauseInProgress:
						positionMatch = self._regex_M114Response.search(line)
						if positionMatch:
							self._positionWhenPaused = (
								float(positionMatch.group(1)),
								float(positionMatch.group(2)),
								float(positionMatch.group(3)),
								float(positionMatch.group(4))
							)

							self.sendCommand("G1 F9000 X0 Y0 Z%.4f E%.4f" % (self._positionWhenPaused[2] + 15, self._positionWhenPaused[3] - 5))
							self.sendCommand("_apCommand_PAUSE")
							self._pauseInProgress = False

				### Printing
				elif self._state == self.STATE_PRINTING:
					if line == "" and time.time() > timeout:
						self._serialLoggerEnabled and self._log("Read communication timeout during printing, listen again")
						#we reset the timeout and try to listen again.
						#we could be executing a long movement, a G29 command or some other thing longer than the timeout
						timeout = getNewTimeout("communication")
						continue

					# if self.isSdPrinting():
					# 	if time.time() > tempRequestTimeout and not self._heatingUp:
					# 		self._sendCommand("M105")
					# 		tempRequestTimeout = getNewTimeout("temperature")

					# 	if time.time() > sdStatusRequestTimeout and not self._heatingUp:
					# 		self._sendCommand("M27")
					# 		sdStatusRequestTimeout = getNewTimeout("sdStatus")
					# else:

					# Even when printing request the temperature every 5 seconds.
					if time.time() > tempRequestTimeout:# and not self.isStreaming():
						#It there's already a request for temps, don't add a new one....
						if len(self._commandQueue) == 0 or "M105" not in self._commandQueue[-1]:
							self._commandQueue.appendleft("M105")

						tempRequestTimeout = getNewTimeout("temperature")

					if "ok" in lineLower:
						if self._resendDelta is not None:
							self._resendNextCommand()
						elif len(self._commandQueue) > 0:
							self._sendCommand(self._commandQueue.pop(), True)
						elif self.isPrinting():
							self._sendNextFileCommand()

					elif lineLower.startswith("resend") or lineLower.startswith("rs"):
						self._handleResendRequest(line)

			except:
				self._logger.exception("Something crashed inside the serial connection loop, please report this to AstroPrint:")

				errorMsg = "See astrobox.log for details"
				self._serialLoggerEnabled and self._log(errorMsg)
				self._errorValue = errorMsg
				self._changeState(self.STATE_ERROR)

		self._serialLoggerEnabled and self._log("Connection closed, closing down monitor")

	def _openSerial(self):
		if self._port == 'AUTO':
			from octoprint.util.avr_isp import stk500v2
			from octoprint.util.avr_isp import ispBase

			#self._changeState(self.STATE_DETECT_SERIAL)
			programmer = stk500v2.Stk500v2()
			self._serialLoggerEnabled and self._log("Serial port list: %s" % (str(self._callback.serialList())))
			for p in self._callback.serialList():
				try:
					self._serialLoggerEnabled and self._log("Connecting to: %s" % (p))
					programmer.connect(p)
					self._serial = programmer.leaveISP()
					break
				except ispBase.IspError as (e):
					self._serialLoggerEnabled and self._log("Error while connecting to %s: %s" % (p, str(e)))
					pass
				except:
					self._serialLoggerEnabled and self._log("Unexpected error while connecting to serial port: %s %s" % (p, getExceptionString()))
				programmer.close()
			if self._serial is None:
				self._serialLoggerEnabled and self._log("Failed to autodetect serial port")
				self._errorValue = 'Failed to autodetect serial port.'
				self._changeState(self.STATE_ERROR)
				return False
		elif self._port == 'VIRTUAL':
			from octoprint.util.virtual import VirtualPrinter

			#self._changeState(self.STATE_OPEN_SERIAL)
			self._serial = VirtualPrinter()
		else:
			#self._changeState(self.STATE_OPEN_SERIAL)
			try:
				self._serialLoggerEnabled and self._log("Connecting to: %s" % self._port)
				if self._baudrate == 0:
					self._serial = serial.Serial(str(self._port), 115200, timeout=0.1, writeTimeout=10000, rtscts=self._settings.getBoolean(["serial", "rtsctsFlowControl"]), dsrdtr=self._settings.getBoolean(["serial", "dsrdtrFlowControl"]), xonxoff=self._settings.getBoolean(["serial", "swFlowControl"]))
				else:
					self._serial = serial.Serial(str(self._port), self._baudrate, timeout=self._settings.getFloat(["serial", "timeout", "connection"]), writeTimeout=10000, rtscts=self._settings.getBoolean(["serial", "rtsctsFlowControl"]), dsrdtr=self._settings.getBoolean(["serial", "dsrdtrFlowControl"]), xonxoff=self._settings.getBoolean(["serial", "swFlowControl"]))
			except:
				self._serialLoggerEnabled and self._log("Unexpected error while connecting to serial port: %s %s" % (self._port, getExceptionString()))
				self._errorValue = "Failed to open serial port, permissions correct?"
				self._changeState(self.STATE_ERROR)
				return False
		return True

	def _lowerAndHandleErrors(self, line):
		# No matter the state, if we see an error, goto the error state and store the error for reference.
		if line.startswith('Error:'):
			#Oh YEAH, consistency.
			# Marlin reports an MIN/MAX temp error as "Error:x\n: Extruder switched off. MAXTEMP triggered !\n"
			#	But a bed temp error is reported as "Error: Temperature heated bed switched off. MAXTEMP triggered !!"
			#	So we can have an extra newline in the most common case. Awesome work people.
			if self._regex_minMaxError.match(line):
				line = line.rstrip() + self._readline()
			#Skip the communication errors, as those get corrected.

			line_lower = line.lower()

			if 'checksum mismatch' in line_lower \
				or 'wrong checksum' in line_lower \
				or 'line number is not last line number' in line_lower \
				or 'expected line' in line_lower \
				or 'no line number with checksum' in line_lower \
				or 'no checksum with line number' in line_lower \
				or 'format error' in line_lower \
				or 'missing checksum' in line_lower:
				pass
			elif not self.isError():
				self._errorValue = line[6:]
				self._changeState(self.STATE_ERROR)

		else:
			line_lower = line.lower()

		return line, line_lower

	def _readline(self):
		if self._serial == None:
			return None

		try:
			ret = self._serial.readline()

		except:
			self._serialLoggerEnabled and self._log("Unexpected error while reading serial port: %s" % (getExceptionString()))
			self._errorValue = getExceptionString()
			self.close(True)
			return None

		if ret == '':
		#	self._serialLoggerEnabled and self._log("Recv: TIMEOUT")
			return ''

		self._serialLoggerEnabled and self._log("Recv: %s" % sanitizeAscii(ret))

		if self._callback.broadcastTraffic > 0:
			self._callback.doTrafficBroadcast('r', ret) #sanitizeAscii(ret))

		return ret

	def _sendNextFileCommand(self):
		line = self._getNextFileCommand()
		if line:
			self._sendCommand(line, True)
			self._callback.mcProgress()

	def _getNextFileCommand(self):
		line = self._currentFile.getNext()
		if line is None:
			# if self.isStreaming():
			# 	self._sendCommand("M29")

			# 	remote = self._currentFile.getRemoteFilename()
			# 	payload = {
			# 		"local": self._currentFile.getLocalFilename(),
			# 		"remote": remote,
			# 		"time": self.getPrintTime()
			# 	}

			# 	self._currentFile = None
			# 	self._changeState(self.STATE_OPERATIONAL)
			# 	self._callback.mcFileTransferDone(remote)
			# 	eventManager().fire(Events.TRANSFER_DONE, payload)
			# 	self.refreshSdFiles()
			# else:

			payload = {
				"file": self._currentFile.getFilename(),
				"filename": os.path.basename(self._currentFile.getFilename()),
				"origin": self._currentFile.getFileLocation(),
				"time": self.getPrintTime(),
				"layerCount": self._currentLayer
			}
			self._callback.mcPrintjobDone()
			self._changeState(self.STATE_OPERATIONAL)
			eventManager().fire(Events.PRINT_DONE, payload)
			return None

		return line

	def _handleResendRequest(self, line):
		lineToResend = None
		try:
			lineToResend = int(line.replace("N:", " ").replace("N", " ").replace(":", " ").split()[-1])
		except:
			if "rs" in line:
				lineToResend = int(line.split()[1])

		if lineToResend is not None:
			linesStored = len(self._lastLines)

			if linesStored == 1 and "M110 N0" in self._lastLines[0]:
				self._resendDelta = 1
			else:
				self._resendDelta = self._currentLine - lineToResend

			if self._resendDelta > linesStored or linesStored == 0 or self._resendDelta <= 0:
				self._errorValue = "Printer requested line %d but no sufficient history is available, can't resend [Delta: %d, History: %d]" % (lineToResend, self._resendDelta, linesStored)
				self._logger.warn(self._errorValue)
				if self.isPrinting():
					# abort the print, there's nothing we can do to rescue it now
					self._callback.disableMotorsAndHeater()
					self._changeState(self.STATE_ERROR)

				else:
					# reset resend delta, we can't do anything about it
					self._resendDelta = None
			#else:
			#	self._resendNextCommand()

	def _resendNextCommand(self):
		cmd = self._lastLines[ -self._resendDelta ]
		lineNumber = self._currentLine - self._resendDelta
		self._logger.debug("Resending line %d, delta is %d, history log has %s items" % (lineNumber, self._resendDelta, len(self._lastLines)))

		self._doSendWithChecksum(cmd, lineNumber)

		self._resendDelta -= 1
		if self._resendDelta <= 0:
			self._resendDelta = None

	def _sendCommand(self, cmd, sendChecksum=False):
		if self._serial is None:
			return

		#if not self.isStreaming():
		gcode = self._regex_command.search(cmd)
		if gcode:
			gcode = gcode.group(1)

			if gcode in gcodeToEvent:
				eventManager().fire(gcodeToEvent[gcode])

			gcodeHandler = "_gcode_" + gcode
			if hasattr(self, gcodeHandler):
				cmd = getattr(self, gcodeHandler)(cmd)

		elif cmd.startswith('_apCommand_'):
			#see if it's an AstroPrint Command
			if hasattr(self, cmd):
				cmd = getattr(self, cmd)(cmd)

		if cmd is not None:
			if sendChecksum: # or self._alwaysSendChecksum:
				self._addToLastLines(cmd)
				self._doSendWithChecksum(cmd, self._getNewLineNumber())
			else:
				self._doSend(cmd)

	def _getNewLineNumber(self):
		with self._newLineNumberLock:
			line = self._currentLine
			self._currentLine += 1
			return line

	def _resetLineNumber(self, new):
		with self._newLineNumberLock:
			self._currentLine = new

	def _doSendWithChecksum(self, cmd, lineNumber):
		self._logger.debug("Sending cmd '%s' with lineNumber %r" % (cmd, lineNumber))

		commandToSend = "N%d %s" % (lineNumber, cmd)
		checksum = reduce(lambda x,y:x^y, map(ord, commandToSend))
		commandToSend = "%s*%d" % (commandToSend, checksum)
		self._doSend(commandToSend)

	def _doSend(self, cmd):
		#make sure sends are done orderly
		with self._sendingLock:
			self._serialLoggerEnabled and self._log("Send: %s" % cmd)
			retriesLeft = 5
			while True:
				try:
					self._serial.write(cmd + '\n')

					if self._callback.broadcastTraffic > 0:
						self._callback.doTrafficBroadcast('s', cmd)

					break

				except serial.SerialTimeoutException:
					retriesLeft -= 1

					if retriesLeft == 0:
						self._serialLoggerEnabled and self._log("No more retries left. Closing the connection")
						self._errorValue = "Unable to send data"
						self.close(True)
						break
					else:
						self._serialLoggerEnabled and self._log("Serial Timeout while sending data. Retries left: %d" % retriesLeft)
						time.sleep(0.5)

				except:
					self._serialLoggerEnabled and self._log("Unexpected error while writing serial port: %s" % (getExceptionString()))
					self._errorValue = getExceptionString()
					self.close(True)
					break

	def _gcode_M220(self, cmd):
		speedMatch = self._regex_paramSInt.search(cmd)
		if speedMatch:
			speed = int(speedMatch.group(1))
			if self._printingSpeed != speed:
				self._printingSpeed = speed
				self._callback.mcPrintingSpeedChange(speed)
		return cmd

	def _gcode_M221(self, cmd):
		flowMatch = self._regex_paramSInt.search(cmd)
		if flowMatch:
			flow = int(flowMatch.group(1))
			if self._printingFlow != flow:
				self._printingFlow = flow
				self._callback.mcPrintingFlowChange(flow)
		return cmd

	def _gcode_T(self, cmd):
		toolMatch = self._regex_paramTInt.search(cmd)
		if toolMatch:
			tool = int(toolMatch.group(1))
			if self._currentTool != tool:
				oldTool = self._currentTool

				self._materialCounter.changeActiveTool(str(tool), str(oldTool))
				self._currentTool = tool
				self._callback.mcToolChange(tool, oldTool)
		return cmd

	def _gcode_G92(self, cmd):
		# At the moment this command is only relevant in Absolute Extrusion Mode
		if self._materialCounter.extrusionMode == MaterialCounter.EXTRUSION_MODE_ABSOLUTE:
			eValue = None

			if cmd.strip() == 'G92': #A simple G92 command resets all axis so E is now set to 0
				eValue = 0
			elif 'E' in cmd:
				match = self._regex_paramEFloat.search(cmd)
				if match:
					try:
						eValue = float(match.group(1))

					except ValueError:
						pass

			if eValue is not None:
				#There has been an E reset
				self._materialCounter.resetExtruderLength(eValue)

		return cmd

	def _gcode_G0(self, cmd):
		if 'E' in cmd:
			match = self._regex_paramEFloat.search(cmd)
			if match:
				try:
					self._materialCounter.reportExtrusion(float(match.group(1)))

				except ValueError:
					pass

		if 'Z' in cmd:
			match = self._regex_paramZFloat.search(cmd)
			if match:
				try:
					z = float(match.group(1))
					if self._currentZ != z:
						self._currentZ = z
						self._callback.mcZChange(z)

				except ValueError:
					pass

		elif self._state == self.STATE_PRINTING and self._currentZ != self._lastLayerHeight and self._regex_extrusion.search(cmd) != None:
			if self._currentZ > self._lastLayerHeight:
				self._currentLayer += 1
				self._callback.mcLayerChange(self._currentLayer)

			self._lastLayerHeight = self._currentZ

		return cmd

	_gcode_G1 = _gcode_G0

	def _gcode_M0(self, cmd):
		self.setPause(True)
		return "M105" # Don't send the M0 or M1 to the machine, as M0 and M1 are handled as an LCD menu pause.
	_gcode_M1 = _gcode_M0

	def _gcode_M104(self, cmd):
		toolNum = self._currentTool
		toolMatch = self._regex_paramTInt.search(cmd)
		if toolMatch:
			toolNum = int(toolMatch.group(1))
		match = self._regex_paramSInt.search(cmd)
		if match:
			try:
				target = float(match.group(1))
				if toolNum in self._temp.keys() and self._temp[toolNum] is not None and isinstance(self._temp[toolNum], tuple):
					actual, oldTarget = self._temp[toolNum]
					self._temp[toolNum] = (actual, target)
				else:
					self._temp[toolNum] = (None, target)
			except ValueError:
				pass
		return cmd

	def _gcode_M140(self, cmd):
		match = self._regex_paramSInt.search(cmd)
		if match:
			try:
				target = float(match.group(1))
				if self._bedTemp is not None and isinstance(self._bedTemp, tuple):
					actual, oldTarget = self._bedTemp
					self._bedTemp = (actual, target)
				else:
					self._bedTemp = (None, target)
			except ValueError:
				pass
		return cmd

	def _gcode_M109(self, cmd):
		self._heatingUp = True
		self._callback.mcHeatingUpUpdate(self._heatingUp)
		self._heatupWaitStartTime = time.time()
		return self._gcode_M104(cmd)

	def _gcode_M190(self, cmd):
		self._heatingUp = True
		self._callback.mcHeatingUpUpdate(self._heatingUp)
		self._heatupWaitStartTime = time.time()
		return self._gcode_M140(cmd)

	def _gcode_M110(self, cmd):
		newLineNumber = None
		match = self._regex_paramNInt.search(cmd)
		if match:
			try:
				newLineNumber = int(match.group(1))
			except:
				pass
		else:
			newLineNumber = 0

		# send M110 command with new line number
		self._resetLineNumber(newLineNumber + 1)

		# after a reset of the line number we have no way to determine what line exactly the printer now wants
		self._lastLines.clear()
		self._resendDelta = None
		self._addToLastLines(cmd)

		self._doSendWithChecksum(cmd, newLineNumber)

		return None

	def _gcode_M112(self, cmd): # It's an emergency what todo? Canceling the print should be the minimum
		self.cleanPrintingVars()
		self.cancelPrint()
		return cmd

	def _gcode_M82(self, cmd): #Set to absolute extrusion mode
		self._materialCounter.changeExtrusionMode(MaterialCounter.EXTRUSION_MODE_ABSOLUTE)
		return cmd

	def _gcode_M83(self, cmd): #Set to relative extrusion mode
		self._materialCounter.changeExtrusionMode(MaterialCounter.EXTRUSION_MODE_RELATIVE)
		return cmd

	# In Marlin G91 and G90 also change the relative nature of extrusion
	_gcode_G90 = _gcode_M82 #Set Absolute
	_gcode_G91 = _gcode_M83 #Set Relative

	#The following are internal commands to ensure an orderly pause and shutdown sequence

	def _apCommand_CANCEL(self, cmd):
		self.cleanPrintingVars()
		self.cancelPrint()
		return None

	def _apCommand_PAUSE(self, cmd):
		eventManager().fire(Events.PRINT_PAUSED, {
			"file": self._currentFile.getFilename(),
			"filename": os.path.basename(self._currentFile.getFilename()),
			"origin": self._currentFile.getFileLocation()
		})

		self._changeState(self.STATE_PAUSED)
		return None

### MachineCom callback ################################################################################################

class MachineComPrintCallback(object):
	def mcLog(self, message):
		pass

	def mcTempUpdate(self, temp, bedTemp):
		pass

	def mcHeatingUpUpdate(self, value):
		pass

	def mcStateChange(self, state):
		pass

	def mcMessage(self, message):
		pass

	def mcProgress(self):
		pass

	def mcZChange(self, newZ):
		pass

	def mcToolChange(self, newTool, oldTool):
		pass

	def mcLayerChange(self, layer):
		pass

	def mcSdStateChange(self, sdReady):
		pass

	def mcSdFiles(self, files):
		pass

	def mcSdPrintingDone(self):
		pass

	def mcFileTransferStarted(self, filename, filesize):
		pass

	def mcReceivedRegisteredMessage(self, command, message):
		pass

### Printing file information classes ##################################################################################

class PrintingFileInformation(object):
	"""
	Encapsulates information regarding the current file being printed: file name, current position, total size and
	time the print started.
	Allows to reset the current file position to 0 and to calculate the current progress as a floating point
	value between 0 and 1.
	"""

	def __init__(self, filename):
		self._filename = filename
		self._filepos = 0
		self._filesize = None
		self._startTime = None

	def getStartTime(self):
		return self._startTime

	def getFilename(self):
		return self._filename

	def getFilesize(self):
		return self._filesize

	def getFilepos(self):
		return self._filepos

	def getFileLocation(self):
		return FileDestinations.LOCAL

	def getProgress(self):
		"""
		The current progress of the file, calculated as relation between file position and absolute size. Returns -1
		if file size is None or < 1.
		"""
		if self._filesize is None or not self._filesize > 0:
			return -1
		return float(self._filepos) / float(self._filesize)

	def reset(self):
		"""
		Resets the current file position to 0.
		"""
		self._filepos = 0

	def start(self):
		"""
		Marks the print job as started and remembers the start time.
		"""
		self._startTime = time.time()

class PrintingSdFileInformation(PrintingFileInformation):
	"""
	Encapsulates information regarding an ongoing print from SD.
	"""

	def __init__(self, filename, filesize):
		PrintingFileInformation.__init__(self, filename)
		self._filesize = filesize

	def setFilepos(self, filepos):
		"""
		Sets the current file position.
		"""
		self._filepos = filepos

	def getFileLocation(self):
		return FileDestinations.SDCARD

class PrintingGcodeFileInformation(PrintingFileInformation):
	"""
	Encapsulates information regarding an ongoing direct print. Takes care of the needed file handle and ensures
	that the file is closed in case of an error.
	"""

	def __init__(self, filename):
		PrintingFileInformation.__init__(self, filename)

		self._filehandle = None

		self._filesetMenuModehandle = None
		self._currentTool = 0
		self._regex_toolCommand = re.compile("^T(\d+)")

		if not os.path.exists(self._filename) or not os.path.isfile(self._filename):
			raise IOError("File %s does not exist" % self._filename)
		self._filesize = os.stat(self._filename).st_size

	def start(self):
		"""
		Opens the file for reading and determines the file size. Start time won't be recorded until 100 lines in
		"""
		self._filehandle = open(self._filename, "r")
		self._startTime = time.time()

	def getNext(self):
		"""
		Retrieves the next line for printing.
		"""
		if self._filehandle is None:
			raise ValueError("File %s is not open for reading" % self._filename)

		try:
			processedLine = None
			while processedLine is None:
				if self._filehandle is None:
					# file got closed just now
					return None
				line = self._filehandle.readline()
				if not line:
					self._filehandle.close()
					self._filehandle = None
				processedLine = self._processLine(line)
			self._filepos = self._filehandle.tell()

			return processedLine
		except Exception as (e):
			if self._filehandle is not None:
				self._filehandle.close()
				self._filehandle = None
			raise e

	def _processLine(self, line):
		commentPos = line.find(";")

		if commentPos >= 0:
			if commentPos == 0:
				return None #The whole line is a comment
			else:
				line = line[0:commentPos]

		line = line.strip()
		if len(line) > 0:
			toolMatch = self._regex_toolCommand.match(line)
			if toolMatch is not None:
				# track tool changes
				self._currentTool = int(toolMatch.group(1))

			return line
		else:
			return None

class StreamingGcodeFileInformation(PrintingGcodeFileInformation):
	def __init__(self, path, localFilename, remoteFilename):
		PrintingGcodeFileInformation.__init__(self, path, None)
		self._localFilename = localFilename
		self._remoteFilename = remoteFilename

	def start(self):
		PrintingGcodeFileInformation.start(self)
		self._startTime = time.time()

	def getLocalFilename(self):
		return self._localFilename

	def getRemoteFilename(self):
		return self._remoteFilename
