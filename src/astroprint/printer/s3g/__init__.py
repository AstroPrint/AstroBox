# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import logging

from octoprint.events import eventManager, Events

from astroprint.printer import Printer 

class PrinterS3g(Printer):
	driverName = 's3g'

	_comm = None
	_port = None
	_baudrate = None
	_errorValue = ''

	def __init__(self, fileManager):
		self._logger = logging.getLogger(__name__)
		super(PrinterS3g, self).__init__(fileManager)

	def connect(self, port, baudrate = None):
		import makerbot_driver

		self._changeState(self.STATE_CONNECTING)
		self._errorValue = ''
		self._port = port
		self._baudrate = baudrate
		self._comm = makerbot_driver.s3g.from_filename(port, threading.Condition(), baudrate)
		
		try:
			self._comm.clear_buffer()
			self._changeState(self.STATE_OPERATIONAL)

		except makerbot_driver.errors.TransmissionError as e:
			self._logger.error('Error connecting to printer %s' % e)
			self._changeState(self.STATE_ERROR)
			self._errorValue = "TransmissionError"
			self._comm = None

	def disconnect(self):
		if self._comm and self._comm.is_open():
			self._comm.close()
			self._comm = None
			self._changeState(self.STATE_CLOSED)
			eventManager().fire(Events.DISCONNECTED)

	def isReady(self):
		return self.isOperational() #and not self._comm.isStreaming()

	def isHeatingUp(self):
		#return self._comm is not None and self._comm.isHeatingUp()
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
			return "Error: %s" % (self.getShortErrorString())
		if self._state == self.STATE_TRANSFERING_FILE:
			return "Transfering file to SD"
		return "?%d?" % (self._state)

	def getCurrentConnection(self):
		return self.getStateString(), self._port, self._baudrate

	def getShortErrorString(self):
		if len(self._errorValue) < 50:
			return self._errorValue
		return self._errorValue[:50] + "..."

	def getErrorString(self):
		return self._errorValue

	def _changeState(self, newState):
		if self._state == newState:
			return

		oldState = self.getStateString()
		self._state = newState
		self._logger.info('Changing monitoring state from \'%s\' to \'%s\'' % (oldState, self.getStateString()))

		# forward relevant state changes to gcode manager
		if self._comm is not None and oldState == self.STATE_PRINTING:
			#if self._selectedFile is not None:
			#	if state == self.STATE_OPERATIONAL:
			#		self._fileManager.printSucceeded(self._selectedFile["filename"], self._comm.getPrintTime())
			#	elif state == self.STATE_CLOSED or state == self.STATE_ERROR or state == self.STATE_CLOSED_WITH_ERROR:
			#		self._fileManager.printFailed(self._selectedFile["filename"], self._comm.getPrintTime())
			self._fileManager.resumeAnalysis() # printing done, put those cpu cycles to good use
		elif self._comm is not None and newState == self.STATE_PRINTING:
			self._fileManager.pauseAnalysis() # do not analyse gcode while printing

		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})




