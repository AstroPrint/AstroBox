# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import time
import datetime
import threading
import logging
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

		self._selectedFile = None

		# comm
		self._comm = None

		super(PrinterMarlin, self).__init__()

	def rampdown(self):
		if self._comm:	
			self._comm.close()
			self._comm.thread.join()
			self._comm = None

		super(PrinterMarlin, self).rampdown()

	def disableMotorsAndHeater(self):
		self.setTemperature('bed', 5)
		self.setTemperature('tool', 5)
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

	#~~ callback from gcodemanager

	def sendUpdateTrigger(self, type):
		if type == "gcodeFiles" and self._selectedFile:
			self._setJobData(self._selectedFile["filename"],
				self._selectedFile["filesize"],
				self._selectedFile["sd"])

	#~~ printer object API implementation

	def serialList(self):
		ports = {}
		if platform.startswith('linux'):
			from usbid.device import device_list

			for p in device_list():
				if p.tty:
					ports['/dev/%s' % p.tty] = p.nameProduct

		else:
			for p in serial.tools.list_ports.comports():
				if p[1] != 'n/a':
					ports[p[0]] = p[1]

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
		self.commands(["G91", "G1 %s%.4f F%d" % (axis.upper(), amount, movementSpeed[axis]), "G90"])

	def home(self, axes):
		self.commands(["G91", "G28 %s" % " ".join(map(lambda x: "%s0" % x.upper(), axes)), "G90"])

	def extrude(self, tool, amount, speed=None):
		if not speed:
			speed = settings().get(["printerParameters", "movementSpeed", "e"])

		self.commands(["G91", "G1 E%s F%d" % (amount, speed), "G90"])

	def changeTool(self, tool):
		try:
			toolNum = int(tool[len("tool"):])
			self.command("T%d" % toolNum)
		except ValueError:
			pass

	def setTemperature(self, type, value):
		if type.startswith("tool"):
			value = min(value, self._profileManager.data.get('max_nozzle_temp'))
			if settings().getInt(["printerParameters", "numExtruders"]) > 1:
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

		self._comm.startPrint()

	def togglePausePrint(self):
		"""
		 Pause the current printjob.
		"""
		if self._comm is None:
			return

		wasPaused = self._comm.isPaused()

		self._comm.setPause(not wasPaused)

		#the functions already check if there's a timelapse in progress
		if wasPaused:
			self._cameraManager.resume_timelapse()
		else:
			self._cameraManager.pause_timelapse()

	def cancelPrint(self, disableMotorsAndHeater=True):
		"""
		 Cancel the current printjob.
		"""
		if not super(PrinterMarlin, self).cancelPrint(disableMotorsAndHeater):
			return

		#flush the Queue
		commandQueue = self._comm._commandQueue
		commandQueue.clear()

		# reset progress, height, print time
		self._setCurrentZ(None)
		self._setProgressData(None, None, None, None, None)

		# mark print as failure
		if self._selectedFile is not None:
			self._fileManager.printFailed(self._selectedFile["filename"], self._comm.getPrintTime())
			payload = {
				"file": self._selectedFile["filename"],
				"origin": FileDestinations.LOCAL
			}
			if self._selectedFile["sd"]:
				payload["origin"] = FileDestinations.SDCARD
			eventManager().fire(Events.PRINT_FAILED, payload)
			self._selectedFile = None

		self._comm.cancelPrint()

		#self._comm._sendCommand("M112");

		#don't send home command, some printers don't have stoppers.
		#self.home(['x','y'])
		self.commands(["G92 E0", "G1 X0 Y0 E-2.0 F3000 S1", "G92"]) # this replaces home

		if disableMotorsAndHeater:
			self.disableMotorsAndHeater()

	#~~ state monitoring

	def _setState(self, state):
		self._state = state
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

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

	def mcMessage(self, message):
		"""
		 Callback method for the comm object, called upon message exchanges via serial.
		 Stores the message in the message buffer, truncates buffer to the last 300 lines.
		"""
		self._addMessage(message)

	def mcSdStateChange(self, sdReady):
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def mcSdFiles(self, files):
		eventManager().fire(Events.UPDATED_FILES, {"type": "gcode"})
		self._sdFilelistAvailable.set()

	def mcFileSelected(self, filename, filesize, sd):
		self._setJobData(filename, filesize, sd)
		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

		if self._printAfterSelect:
			self.startPrint()

	def mcPrintjobDone(self):
		super(PrinterMarlin, self).mcPrintjobDone()
		self.disableMotorsAndHeater()

	def mcFileTransferStarted(self, filename, filesize):
		self._sdStreaming = True

		self._setJobData(filename, filesize, True)
		self._setProgressData(0.0, 0, 0, None, 1)
		self._stateMonitor.setState({"state": self._state, "stateString": self.getStateString(), "flags": self._getStateFlags()})
		#self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def mcFileTransferDone(self, filename):
		self._sdStreaming = False

		if self._streamingFinishedCallback is not None:
			# in case of SD files, both filename and absolutePath are the same, so we set the (remote) filename for
			# both parameters
			self._streamingFinishedCallback(filename, filename, FileDestinations.SDCARD)

		self._setCurrentZ(None)
		self._setJobData(None, None, None)
		self._setProgressData(None, None, None, None, None)
		self._stateMonitor.setState({"state": self._state, "stateString": self.getStateString(), "flags": self._getStateFlags()})
		#self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def mcReceivedRegisteredMessage(self, command, output):
		self._sendFeedbackCommandOutput(command, output)

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
