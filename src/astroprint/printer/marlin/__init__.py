# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com> based on previous work by Gina Häußge"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import time
import os
import datetime
import threading
import logging
import re
import serial.tools.list_ports

from sys import platform

import octoprint.util as util

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from astroprint.printer import Printer
from astroprint.printfiles.gcode import PrintFileManagerGcode
from astroprint.printfiles import FileDestinations

class PrinterMarlin(Printer):
	driverName = 'marlin'
	allowTerminal = True

	_fileManagerClass = PrintFileManagerGcode

	def __init__(self):
		from collections import deque

		# state
		# TODO do we really need to hold the temperature here?
		self._targetTemp = None
		self._targetBedTemp = None
		self._tempBacklog = []

		self._latestMessage = None
		self._messageBacklog = []

		self._latestLog = None
		self._log = deque([], 300)
		self._logBacklog = []

		self._layerCount = None
		self._estimatedPrintTime = None

		self._printId = None

		# sd handling
		self._sdPrinting = False
		self._sdStreaming = False
		self._sdFilelistAvailable = threading.Event()
		self._streamingFinishedCallback = None

		# comm
		self._comm = None

		self.estimatedTimeLeft = None
		self.timePercentPreviousLayers = 0

		super(PrinterMarlin, self).__init__()

	def rampdown(self):
		if self._comm:
			self._comm.close()
			self._comm.thread.join()
			self._comm = None

		super(PrinterMarlin, self).rampdown()

	def disableMotorsAndHeater(self):
		self.setTemperature('bed', 0)
		for i in range(self._profileManager.data.get('extruder_count')):
			self.setTemperature('tool%d' % i, 0)
		self.commands(["M84", "M106 S0"]); #Motors Off, Fan off

	#~~ callback handling

	def _sendTriggerUpdateCallbacks(self, type):
		for callback in self._callbacks:
			try: callback.sendEvent(type)
			except: pass

	def _sendFeedbackCommandOutput(self, name, output):
		for callback in self._callbacks:
			try: callback.sendFeedbackCommandOutput(name, output)
			except: pass

	#~~ callback from gcode received

	def doTrafficBroadcast(self, direction, content):
		for callback in self._callbacks:
			try: callback.sendCommsData(direction, content)
			except: pass

	#~~ callback from gcodemanager

	def sendUpdateTrigger(self, type):
		if type == "gcodeFiles" and self._selectedFile:
			self._setJobData(self._selectedFile["filename"],
				self._selectedFile["filesize"],
				self._selectedFile["sd"])

	#~~ printer object API implementation

	def serialList(self):
		ports = {}
		if platform == "darwin":
			regex = re.compile(r"\/dev\/cu\.usb(?:serial|modem)[\w-]+")
		elif "linux" in platform:
			#https://rfc1149.net/blog/2013/03/05/what-is-the-difference-between-devttyusbx-and-devttyacmx/
			regex = re.compile(r"\/dev\/tty(?:ACM|USB|)[0-9]+")

		for p in serial.tools.list_ports.comports():
			if regex.match(p.device) is not None:
				ports[p.device] = p.product or "Unknown serial device"

		return ports

	def baudrateList(self):
		ret = [250000, 230400, 115200, 57600, 38400, 19200, 9600]
		prev = settings().getInt(["serial", "baudrate"])
		if prev in ret:
			ret.remove(prev)
			ret.insert(0, prev)
		return ret

	def connect(self, port=None, baudrate=None):
		"""
		 Connects to the printer. If port and/or baudrate is provided, uses these settings, otherwise autodetection
		 will be attempted.
		"""

		if self._comm is not None:
			self._comm.close()

		import astroprint.printer.marlin.comm as comm

		self._comm = comm.MachineCom(port, baudrate, callbackObject=self)

	def disconnect(self):
		"""
		 Closes the connection to the printer.
		"""
		if self._comm is not None:
			self._comm.close()
		self._comm = None
		eventManager().fire(Events.DISCONNECTED)

	def command(self, command):
		"""
		 Sends a single gcode command to the printer.
		"""
		self.commands([command])

	def commands(self, commands):
		"""
		 Sends multiple gcode commands (provided as a list) to the printer.
		"""
		if self._comm is None:
			return

		for command in commands:
			self._comm.sendCommand(command)

	def fan(self, tool, speed):
		self.command("M106 S%d" % max(speed, speed))

	def jog(self, axis, amount):
		movementSpeed = settings().get(["printerParameters", "movementSpeed", ["x", "y", "z"]], asdict=True)
		self.commands(["G91", "G1 %s%.4f F%d" % (axis.upper(), self.jogAmountWithPrinterProfile(axis, amount), movementSpeed[axis]), "G90"])

	def home(self, axes):
		self.commands(["G91", "G28 %s" % " ".join(map(lambda x: "%s0" % x.upper(), axes)), "G90"])

	def extrude(self, tool, amount, speed=None):
		if self._comm:
			if speed:
				#the UI sends mm/s, we need to transfer it to mm/min
				speed *= 60
			else:
				speed = settings().get(["printerParameters", "movementSpeed", "e"])

			selectedTool = self._comm.getSelectedTool()
			if tool is not None and selectedTool != tool:
				self.commands(["G91", "T%d" % tool, "G1 E%s F%d" % (amount, speed), "T%d" % selectedTool, "G90"])
			else:
				self.commands(["G91", "G1 E%s F%d" % (amount, speed), "G90"])

	def changeTool(self, tool):
		try:
			self.command("T%d" % tool)
		except ValueError:
			pass

	def sendRawCommand(self, command):
		self._comm.sendCommand(command)

	def setTemperature(self, type, value):
		if type.startswith("tool"):
			value = min(value, self._profileManager.data.get('max_nozzle_temp'))
			if self._profileManager.data.get('extruder_count') > 1:
				try:
					toolNum = int(type[len("tool"):])
					self.command("M104 T%d S%f" % (toolNum, value))
				except ValueError:
					pass
			else:
				self.command("M104 S%f" % value)
		elif type == "bed":
			self.command("M140 S%f" % min(value, self._profileManager.data.get('max_bed_temp')))

	def selectFile(self, filename, sd, printAfterSelect=False):
		if not super(PrinterMarlin, self).selectFile(filename, sd, printAfterSelect):
			return False

		return self._comm.selectFile(filename, sd)

	def unselectFile(self):
		if not super(PrinterMarlin, self).unselectFile():
			return False

		return self._comm.unselectFile()

	def startPrint(self):
		if not super(PrinterMarlin, self).startPrint():
			return

		self.estimatedTimeLeft = None
		self.timePercentPreviousLayers = 0
		self._comm.startPrint()

	def executeCancelCommands(self, disableMotorsAndHeater):
		"""
		 Cancel the current printjob.
		"""

		self._comm._cancelInProgress = True

		#flush the Queue
		commandQueue = self._comm._commandQueue
		commandQueue.clear()

		# reset progress, height, print time
		self._setCurrentZ(None)
		self._setProgressData(None, None, None, None, None)

		# mark print as failure
		if self._selectedFile is not None:
			eventManager().fire(Events.PRINT_CANCELLED, {
				"file": self._selectedFile["filename"],
				"filename": os.path.basename(self._selectedFile["filename"]),
				"origin": FileDestinations.LOCAL,
			})

			self._fileManager.printFailed(self._selectedFile["filename"], self._comm.getPrintTime())
			payload = {
				"file": self._selectedFile["filename"],
				"origin": FileDestinations.LOCAL
			}
			if self._selectedFile["sd"]:
				payload["origin"] = FileDestinations.SDCARD
			eventManager().fire(Events.PRINT_FAILED, payload)
			self._selectedFile = None

		#prepare cancel commands
		cancelCommands = []
		for c in self._profileManager.data.get('cancel_gcode'):
			if ";" in c:
				c = c[0:c.find(";")]

			c = c.strip()
			if len(c) > 0:
				cancelCommands.append(c)

		self.commands((cancelCommands or ['G28 X Y'] ) + ['M110 N0'] );

		if disableMotorsAndHeater:
			self.disableMotorsAndHeater()

		self.commands(['_apCommand_CANCEL'])

	#~~ state monitoring

	def _setState(self, state):
		self._state = state
		self.refreshStateData()

	def _addLog(self, log):
		self._log.append(log)
		self._stateMonitor.addLog(log)

	def _addMessage(self, message):
		self._messages.append(message)
		self._stateMonitor.addMessage(message)

	#~~ callbacks triggered from self._comm

	def mcLog(self, message):
		"""
		 Callback method for the comm object, called upon log output.
		"""
		self._addLog(message)

	def mcStateChange(self, state):
		"""
		 Callback method for the comm object, called if the connection state changes.
		"""
		oldState = self._state

		# forward relevant state changes to gcode manager
		if self._comm is not None and oldState == self._comm.STATE_PRINTING:
			if self._selectedFile is not None:
				if state == self._comm.STATE_OPERATIONAL:
					self._fileManager.printSucceeded(self._selectedFile["filename"], self._comm.getPrintTime())

				elif state == self._comm.STATE_CLOSED or state == self._comm.STATE_ERROR or state == self._comm.STATE_CLOSED_WITH_ERROR:
					self._fileManager.printFailed(self._selectedFile["filename"], self._comm.getPrintTime())

			self._fileManager.resumeAnalysis() # printing done, put those cpu cycles to good use
		elif self._comm is not None and state == self._comm.STATE_PRINTING:
			self._fileManager.pauseAnalysis() # do not analyse gcode while printing

		self._setState(state)

	def mcLayerChange(self, layer):

		super(PrinterMarlin, self).mcLayerChange(layer)

		try:
			if not layer == 1:
				self.timePercentPreviousLayers += self._comm.timePerLayers[layer-2]['time']
			else:
				self.timePercentPreviousLayers = 0
		except: pass


	def mcProgress(self):
		"""
		 Callback method for the comm object, called upon any change in progress of the printjob.
		 Triggers storage of new values for printTime, printTimeLeft and the current progress.
		"""
		try:
			layerFileUpperPercent = self._comm.timePerLayers[self._currentLayer-1]['upperPercent']

			if self._currentLayer > 1:
				layerFileLowerPercent = self._comm.timePerLayers[self._currentLayer-2]['upperPercent']
			else:
				layerFileLowerPercent = 0

			currentAbsoluteFilePercent = self.getPrintProgress()
			elapsedTime = self.getPrintTime()

			try:
				currentLayerPercent = (currentAbsoluteFilePercent - layerFileLowerPercent) / (layerFileUpperPercent - layerFileLowerPercent)
			except:
				currentLayerPercent = 0

			layerTimePercent = currentLayerPercent * self._comm.timePerLayers[self._currentLayer-1]['time']

			currentTimePercent = self.timePercentPreviousLayers + layerTimePercent

			estimatedTimeLeft = self._comm.totalPrintTime * ( 1.0 - currentTimePercent )

			elapsedTimeVariance = elapsedTime - ( self._comm.totalPrintTime - estimatedTimeLeft)

			adjustedEstimatedTime = self._comm.totalPrintTime + elapsedTimeVariance

			estimatedTimeLeft = ( adjustedEstimatedTime * ( 1.0 - currentTimePercent ) ) / 60

			if self.estimatedTimeLeft and self.estimatedTimeLeft < estimatedTimeLeft:
				estimatedTimeLeft = self.estimatedTimeLeft
			else:
				self.estimatedTimeLeft = estimatedTimeLeft

			self._setProgressData(self.getPrintProgress(), self.getPrintFilepos(), elapsedTime, estimatedTimeLeft, self._currentLayer)

		except Exception, e:
			super(PrinterMarlin, self).mcProgress()


	def mcMessage(self, message):
		"""
		 Callback method for the comm object, called upon message exchanges via serial.
		 Stores the message in the message buffer, truncates buffer to the last 300 lines.
		"""
		self._addMessage(message)

	def mcSdStateChange(self, sdReady):
		self.refreshStateData()

	def mcSdFiles(self, files):
		eventManager().fire(Events.UPDATED_FILES, {"type": "gcode"})
		self._sdFilelistAvailable.set()

	def mcFileSelected(self, filename, filesize, sd):
		self._setJobData(filename, filesize, sd)
		self.refreshStateData()

		if self._printAfterSelect:
			self.startPrint()

	def mcPrintjobDone(self):
		super(PrinterMarlin, self).mcPrintjobDone()
		self.disableMotorsAndHeater()
		self._comm.cleanPrintingVars()

	def mcFileTransferStarted(self, filename, filesize):
		self._sdStreaming = True

		self._setJobData(filename, filesize, True)
		self._setProgressData(0.0, 0, 0, None, 1)
		self.refreshStateData()

	def mcFileTransferDone(self, filename):
		self._sdStreaming = False

		if self._streamingFinishedCallback is not None:
			# in case of SD files, both filename and absolutePath are the same, so we set the (remote) filename for
			# both parameters
			self._streamingFinishedCallback(filename, filename, FileDestinations.SDCARD)

		self._setCurrentZ(None)
		self._setJobData(None, None, None)
		self._setProgressData(None, None, None, None, None)
		self.refreshStateData()

	def mcReceivedRegisteredMessage(self, command, output):
		self._sendFeedbackCommandOutput(command, output)

	def _setJobData(self, filename, filesize, sd):
		super(PrinterMarlin, self)._setJobData(filename, filesize, sd)
		self._comm.totalPrintTime = self._estimatedPrintTime

	#~~ sd file handling

	def getSdFiles(self):
		if self._comm is None or not self._comm.isSdReady():
			return []
		return self._comm.getSdFiles()

	def addSdFile(self, filename, absolutePath, streamingFinishedCallback):
		if not self._comm or self._comm.isBusy() or not self._comm.isSdReady():
			logging.error("No connection to printer or printer is busy")
			return

		self._streamingFinishedCallback = streamingFinishedCallback

		self.refreshSdFiles(blocking=True)
		existingSdFiles = map(lambda x: x[0], self._comm.getSdFiles())

		remoteName = util.getDosFilename(filename, existingSdFiles)
		self._comm.startFileTransfer(absolutePath, filename, remoteName)

		return remoteName

	def deleteSdFile(self, filename):
		if not self._comm or not self._comm.isSdReady():
			return
		self._comm.deleteSdFile(filename)

	def initSdCard(self):
		if not self._comm or self._comm.isSdReady():
			return
		self._comm.initSdCard()

	def releaseSdCard(self):
		if not self._comm or not self._comm.isSdReady():
			return
		self._comm.releaseSdCard()

	def refreshSdFiles(self, blocking=False):
		"""
		Refreshs the list of file stored on the SD card attached to printer (if available and printer communication
		available). Optional blocking parameter allows making the method block (max 10s) until the file list has been
		received (and can be accessed via self._comm.getSdFiles()). Defaults to a asynchronous operation.
		"""
		if not self._comm or not self._comm.isSdReady():
			return
		self._sdFilelistAvailable.clear()
		self._comm.refreshSdFiles()
		if blocking:
			self._sdFilelistAvailable.wait(10000)

	#~~ state reports

	def getStateString(self):
		"""
		 Returns a human readable string corresponding to the current communication state.
		"""
		if self._comm is None:
			return "Offline"
		else:
			return self._comm.getStateString()

	def getCurrentTemperatures(self):
		result = {}
		if self._temp is not None:
			for tool in self._temp.keys():
				result["tool%d" % tool] = {
					"actual": self._temp[tool][0],
					"target": self._temp[tool][1]
					}
		if self._bedTemp is not None:
			result["bed"] = {
				"actual": self._bedTemp[0],
				"target": self._bedTemp[1]
			}

		return result

	def getTemperatureHistory(self):
		return self._temps

	def getCurrentConnection(self):
		if self._comm is None:
			return "Closed", None, None

		port, baudrate = self._comm.getConnection()
		return self._comm.getStateString(), port, baudrate

	def getPrintTime(self):
		return self._comm.getPrintTime()

	def getConsumedFilament(self):
		return self._comm.getConsumedFilament()

	def getTotalConsumedFilament(self):
		return self._comm.getTotalConsumedFilament()

	def getSelectedTool(self):
		return self._comm.getSelectedTool()

	def getPrintProgress(self):
		return self._comm.getPrintProgress()

	def getPrintFilepos(self):
		return self._comm.getPrintFilepos()

	def isReady(self):
		return self.isOperational() and not self._comm.isStreaming()

	def isHeatingUp(self):
		return self._comm is not None and self._comm.isHeatingUp()

	def isStreaming(self):
		return (bool) (self._comm and self._comm.isStreaming())

	def isConnected(self):
		return (bool) (self._comm and self._comm.isOperational())

	def isPaused(self):
		return (bool) (self._comm and self._comm.isPaused())

	def setPause(self, paused):
		if self._comm:
			self._comm.setPause(paused)

	def resetSerialLogging(self):
		if self._comm:
			self._comm.resetSerialLogging()
