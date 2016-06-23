# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import logging
import time
import os

from astroprint.printfiles.gcode import PrintFileManagerGcode
from astroprint.printer import Printer
from astroprint.printfiles import FileDestinations

from octoprint.events import eventManager, Events

class PrinterVirtual(Printer):
	driverName = 'virtual'
	allowTerminal = True

	_fileManagerClass = PrintFileManagerGcode

	def __init__(self):
		self._printing = False
		self._heatingUp = False
		self._temperatureChanger = None
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

		#if self._printJob and self._printJob.isAlive():
		#	raise Exception("A Print Job is still running")

		self._changeState(self.STATE_PRINTING)
		eventManager().fire(Events.PRINT_STARTED, {
			"file": self._currentFile['filename'],
			"filename": os.path.basename(self._currentFile['filename']),
			"origin": self._currentFile['origin']
		})

		#self._printJob = PrintJobS3G(self, self._currentFile)
		#self._printJob.start()

	def cancelPrint(self, disableMotorsAndHeater=True):
		"""
		 Cancel the current printjob.
		"""
		if not super(PrinterVirtual, self).cancelPrint():
			return

		# reset progress, height, print time
		self._setCurrentZ(None)
		self._setProgressData(None, None, None, None, None)

		# mark print as failure
		if self._currentFile is not None:
			self._fileManager.printFailed(self._currentFile["filename"], self.getPrintTime())
			self.unselectFile()
			
		#self._printJob.cancel()

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
			self._changeState(self.STATE_OPERATIONAL)
			self._temperatureChanger = TempsChanger(self)
			self._temperatureChanger.start()

		t = threading.Timer(3.0, doConnect)
		t.start()

	def isConnected(self):
		return self._comm

	def disconnect(self):
		if self._comm:
			self._comm = False

			if self._temperatureChanger:
				self._temperatureChanger.stop()
				self._temperatureChanger = None

			self._changeState(self.STATE_CLOSED)
			eventManager().fire(Events.DISCONNECTED)

	def isReady(self):
		return self._comm and not self.STATE_PRINTING

	def isPaused(self):
		return self._state == self.STATE_PAUSED

	def setPause(self, paused):
		if paused:
			self._changeState(self.STATE_PAUSED)
		else:
			self._changeState(self.STATE_PRINTING)

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
		raise NotImplementedError()

	def getPrintProgress(self):
		raise NotImplementedError()

	def getPrintFilepos(self):
		raise NotImplementedError()

	def getCurrentConnection(self):
		if not self._comm:
			return "Closed", None, None

		return self.getStateString(), 'virtual', 0

	def jog(self, axis, amount):
		self._logger.info('Jog - Axis: %s, Amount: %s', axis, amount)

	def home(self, axes):
		self._logger.info('Home - Axes: %s', ', '.join(axes))

	def fan(self, tool, speed):
		self._logger.info('Fan - Tool: %s, Speed: %s', tool, speed)

	def extrude(self, tool, amount, speed=None):
		self._logger.info('Extrude - Tool: %s, Amount: %s, Speed: %s', tool, amount, speed)

	def setTemperature(self, type, value):
		self._logger.info('Temperature - Type: %s, Value: %s', type, value)
		if self._temperatureChanger:
			self._temperatureChanger.setTarget(type, value)

	def sendRawCommand(self, command):
		self._logger.info('Raw Command - %s', command)

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

		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})


class TempsChanger(threading.Thread):
	def __init__(self, manager):
		self._stopped = False
		self._manager = manager
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

		self._manager._stateMonitor.addTemperature(data)