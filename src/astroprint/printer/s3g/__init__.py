# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import logging
import time

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from astroprint.printer import Printer 

class PrinterS3g(Printer):
	driverName = 's3g'

	_comm = None
	_port = None
	_baudrate = None
	_errorValue = ''
	_botThread = None
	_retries = 5

	_toolHeadCount = None

	def __init__(self, fileManager):
		self._logger = logging.getLogger(__name__)
		super(PrinterS3g, self).__init__(fileManager)

	def __del__(self):
		if self._comm and self._comm.is_open():
			self._comm.close()
			self._comm = None

	def connect(self, port, baudrate = None):
		self._changeState(self.STATE_CONNECTING)
		self._errorValue = ''
		self._port = port
		self._baudrate = baudrate

		self._botThread = threading.Thread(target=self._work)
		self._botThread.daemon = True
		self._botThread.start()

	def disconnect(self):
		if self._comm and self._comm.is_open():
			self._comm.close()
			self._comm = None
			self._botThread = None
			self._toolHeadCount = None
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

	def _work(self):
		import makerbot_driver

		self._comm = makerbot_driver.s3g.from_filename(self._port, threading.Condition())
		
		try:
			self._comm.clear_buffer()
			self._changeState(self.STATE_OPERATIONAL)
			self._toolHeadCount = self._comm.get_toolhead_count()
			self._retries = 5

			while self._comm:
				for i in range(0, self._toolHeadCount):
					self._temp[i] = (self._comm.get_toolhead_temperature(i), self._comm.get_toolhead_target_temperature(i))

				self._bedTemp = (self._comm.get_platform_temperature(0), self._comm.get_platform_target_temperature(0))
				self.mcTempUpdate(self._temp, self._bedTemp)
				time.sleep(1)

		except makerbot_driver.errors.TransmissionError as e:
			if self._comm:
				self._comm.close()
				self._comm = None

			self._logger.error('Error connecting to printer %s' % e)
			self._changeState(self.STATE_ERROR)
			self._errorValue = "TransmissionError"

			if self._retries > 0:
				self._retries -= 1
				self._logger.info('Retrying...')
				self.connect(self._port)

		except makerbot_driver.errors.UnknownResponseError as e:
			if self._comm:
				self._comm.close()
				self._comm = None

			self._changeState(self.STATE_ERROR)
			self._errorValue = "UnknownResponseError"
			self._logger.error('Error connecting to printer %s.' % e)
			if self._retries > 0:
				self._retries -= 1
				self._logger.info('Retrying...')
				self.connect(self._port)

	# ~~~ Printer API ~~~~~

	def home(self, axes):
		if self._comm:
			maximums = []
			minumums = []

			if 'x' in axes:
				maximums.append('X')

			if 'y' in axes:
				maximums.append('Y')

			if 'z' in axes:
				minumums.append('Z')

			if maximums:
				self._comm.find_axes_maximums(maximums, 200, 60)

			if minumums:
				self._comm.find_axes_minimums(minumums, 200, 60)

	def jog(self, axis, amount):
		if self._comm and axis in ['x','y','z']:
			ddAmount = amount * 100

			if axis == 'x':
				position = [ddAmount,0,0,0,0]

			if axis == 'y':
				position = [0,ddAmount,0,0,0]

			if axis == 'z':
				position = [0,0,ddAmount,0,0]

			self._comm.queue_extended_point_new(position, 3000, ['x','y','z','a','b'])

	def fan(self, tool, speed):
		if self._comm:
			self._comm.toggle_fan(tool, speed > 0)

	def extrude(self, amount, speed=None):
		if self._comm:
			if not speed:
				speed = settings().get(["printerParameters", "movementSpeed", "e"])

			self._comm.queue_extended_point_new([0,0,0,-amount * 10, speed ], 3000, ['x','y','z','a','b'])

	def setTemperature(self, type, value):
		if self._comm:
			if type.startswith("tool"):
				value = min(value, self._profileManager.data.get('max_nozzle_temp'))
				if settings().getInt(["printerParameters", "numExtruders"]) > 1:
					try:
						toolNum = int(type[len("tool"):])
						self._comm.set_toolhead_temperature(toolNum, value)
					except ValueError:
						pass
				else:
					self._comm.set_toolhead_temperature(0, value)

			elif type == "bed":
				self._comm.set_platform_temperature(0, min(value, self._profileManager.data.get('max_bed_temp')))

