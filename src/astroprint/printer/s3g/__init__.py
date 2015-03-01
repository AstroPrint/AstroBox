# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import logging
import time
import os
import makerbot_driver.errors

from serial import SerialException

from octoprint.settings import settings
from octoprint.events import eventManager, Events
from octoprint.filemanager.destinations import FileDestinations
from octoprint.util import getExceptionString

from astroprint.printer import Printer 
from astroprint.printer.s3g.printjob import PrintJobS3G

class PrinterS3g(Printer):
	driverName = 's3g'

	_comm = None
	_profile = None
	_gcodeParser = None
	_port = None
	_baudrate = None
	_errorValue = ''
	_botThread = None
	_retries = 5
	_currentFile = None
	_printJob = None
	_heatingUp = False

	_toolHeadCount = None

	def __init__(self, fileManager):
		self._logger = logging.getLogger(__name__)
		super(PrinterS3g, self).__init__(fileManager)

	def __del__(self):
		if self._comm and self._comm.is_open():
			self._comm.close()
			self._comm = None

	def isReady(self):
		return self.isOperational() #and not self._comm.isStreaming()

	def isHeatingUp(self):
		return self._heatingUp

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
			#if self.isSdFileSelected():
			#	return "Printing from SD"
			#elif self.isStreaming():
			#	return "Sending file to SD"
			#else:
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

	def getPrintTime(self):
		if self._currentFile is None or self._currentFile['start_time'] is None:
			return None
		else:
			return time.time() - self._currentFile['start_time']

	def getPrintTimeRemainingEstimate(self):
		printTime = self.getPrintTime()
		if printTime is None:
			return None

		printTime /= 60
		progress = self._currentFile['progress']
		if progress:
			return printTimeTotal - printTime
	
		else:
			return None

	def _changeState(self, newState):
		if self._state == newState:
			return

		oldState = self.getStateString()
		self._state = newState
		self._logger.info('Changing monitoring state from \'%s\' to \'%s\'' % (oldState, self.getStateString()))

		# forward relevant state changes to gcode manager
		if self._comm is not None and oldState == self.STATE_PRINTING:
			#if self._currentFile is not None:
			#	if state == self.STATE_OPERATIONAL:
			#		self._fileManager.printSucceeded(self._currentFile["filename"], self._comm.getPrintTime())
			#	elif state == self.STATE_CLOSED or state == self.STATE_ERROR or state == self.STATE_CLOSED_WITH_ERROR:
			#		self._fileManager.printFailed(self._currentFile["filename"], self._comm.getPrintTime())
			self._fileManager.resumeAnalysis() # printing done, put those cpu cycles to good use
		elif self._comm is not None and newState == self.STATE_PRINTING:
			self._fileManager.pauseAnalysis() # do not analyse gcode while printing

		self._stateMonitor.setState({"text": self.getStateString(), "flags": self._getStateFlags()})

	def _work(self):
		import makerbot_driver.MachineFactory
		
		try:
			result = makerbot_driver.MachineFactory().build_from_port(self._port)

			self._comm = result.s3g
			self._profile = result.profile
			self._gcodeParser = result.gcodeparser

			self._comm.init()
			self._changeState(self.STATE_OPERATIONAL)
			self._toolHeadCount = self._comm.get_toolhead_count()
			self._retries = 5
			self._comm.display_message(0,0,"Powered by\nAstroPrint", 10, True, True, False)

			while self._comm:
				try:
					for i in range(0, self._toolHeadCount):
						self._temp[i] = (self._comm.get_toolhead_temperature(i), self._comm.get_toolhead_target_temperature(i))

					self._bedTemp = (self._comm.get_platform_temperature(0), self._comm.get_platform_target_temperature(0))
					self.mcTempUpdate(self._temp, self._bedTemp)

				except makerbot_driver.errors.BufferOverflowError:
					pass
				
				time.sleep(2)

		except makerbot_driver.errors.TransmissionError as e:
			self.disconnect()

			self._logger.error('Error connecting to printer %s' % e)
			self._changeState(self.STATE_ERROR)
			self._errorValue = "TransmissionError"

			if self._retries > 0:
				self._retries -= 1
				self._logger.info('Retrying...')
				self.connect(self._port)

		except makerbot_driver.errors.UnknownResponseError as e:
			self.disconnect()

			self._changeState(self.STATE_ERROR)
			self._errorValue = "UnknownResponseError"
			self._logger.error('Error connecting to printer %s.' % e)
			if self._retries > 0:
				self._retries -= 1
				self._logger.info('Retrying...')
				self.connect(self._port)

		except SerialException as e:
			self._logger.error(e)
			self._errorValue = "Serial Link failed"
			self._changeState(self.STATE_ERROR)
			eventManager().fire(Events.ERROR, {"error": self.getErrorString()})
			self.disconnect()

	# ~~~ Printer API ~~~~~

	def connect(self, port= None, baudrate = None):
		if port is None:
			port = settings().get(["serial", "port"])

		self.disconnect()
		self._changeState(self.STATE_CONNECTING)
		self._errorValue = ''
		self._port = port
		self._baudrate = baudrate

		self._botThread = threading.Thread(target=self._work)
		self._botThread.daemon = True
		self._botThread.start()

	def isConnected(self):
		return self._comm and self._comm.is_open()

	def disconnect(self):
		if self.isConnected():
			self._comm.close()
			self._comm = None
			self._profile = None
			self._gcodeParser = None
			self._botThread = None
			self._toolHeadCount = None
			self._changeState(self.STATE_CLOSED)
			eventManager().fire(Events.DISCONNECTED)

	def serialList(self):
		from makerbot_driver.MachineDetector import MachineDetector

		detector = MachineDetector()
		machines = detector.get_available_machines()

		ports = {}

		for port in machines:
			m = machines[port]
			ports[port] = detector.get_machine_name_from_vid_pid(m['VID'], m['PID'])

		return ports

	def baudrateList(self):
		return []

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
			position, endstops = self._comm.get_extended_position()

			amount = float(amount)

			if axis == 'x':
				steps = int ( amount * self._profile.values['axes']['X']['steps_per_mm'] )
				position[0] += steps

			if axis == 'y':
				steps = int ( amount * self._profile.values['axes']['Y']['steps_per_mm'] )
				position[1] += steps

			if axis == 'z':
				steps = int ( amount * self._profile.values['axes']['Z']['steps_per_mm'] )
				position[2] += steps

			self._comm.queue_extended_point_classic(position, 500)

	def fan(self, tool, speed):
		if self._comm:
			self._comm.toggle_fan(tool, speed > 0)

	def extrude(self, tool, amount, speed=None):
		if self._comm:
			amount = float(amount)

			position, endstops = self._comm.get_extended_position()

			if tool is None:
				tool = 0

			#find out what axis is this:
			axis = self._profile.values['tools'][str(tool)]['stepper_axis']
			steps = int ( amount * self._profile.values['axes'][axis]['steps_per_mm'] )
			if axis == 'A':
				position[3] += steps
			elif axis == 'B':
				position[4] += steps

			self._comm.queue_extended_point_classic(position, 3000)

	def setTemperature(self, type, value):
		if self._comm:
			try:
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

			except makerbot_driver.errors.BufferOverflowError:
				time.sleep(.2)


	def isStreaming(self):
		# We don't yet support sd card printing on S3G
		return False

	def isPaused(self):
		return self._state == self.STATE_PAUSED

	def setPause(self, pause):
		if self.isStreaming():
			return

		if not pause and self.isPaused():
			self._changeState(self.STATE_PRINTING)

			self._comm.reset()

			eventManager().fire(Events.PRINT_RESUMED, {
				"file": self._currentFile['filanema'],
				"filename": os.path.basename(self._currentFile['filename']),
				"origin": self._currentFile['origin']
			})

		elif pause and self.isPrinting():
			self._changeState(self.STATE_PAUSED)

			self._comm.pause()

			eventManager().fire(Events.PRINT_PAUSED, {
				"file": self._currentFile['filanema'],
				"filename": os.path.basename(self._currentFile['filename']),
				"origin": self._currentFile['origin']
			})

	def selectFile(self, filename, sd, printAfterSelect=False):
		if not super(PrinterS3g, self).selectFile(filename, sd, printAfterSelect):
			return

		if sd:
			raise('Printing from SD card is not supported for the S3G Driver')

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

	def unselectFile(self):
		self._currentFile = None

		if not super(PrinterS3g, self).unselectFile():
			return

	def getPrintTime(self):
		if self._currentFile is None or self._currentFile['start_time'] is None:
			return None
		else:
			return time.time() - self._currentFile['start_time']

	def getPrintFilepos(self):
		if self._currentFile is None:
			return None

		return self._currentFile['position']

	def getPrintProgress(self):
		if self._currentFile is None:
			return None

		return self._currentFile['progress']

	def startPrint(self):
		if not super(PrinterS3g, self).startPrint():
			return

		if not self.isOperational() or self.isPrinting():
			return

		if self._currentFile is None:
			raise ValueError("No file selected for printing")


		if self._printJob and self._printJob.isAlive():
			raise Exception("A Print Job is still running")

		#self._currentLayer  = 0;

		self._changeState(self.STATE_PRINTING)
		eventManager().fire(Events.PRINT_STARTED, {
			"file": self._currentFile['filename'],
			"filename": os.path.basename(self._currentFile['filename']),
			"origin": self._currentFile['origin']
		})

		self._printJob = PrintJobS3G(self, self._currentFile)
		self._printJob.start()

	def cancelPrint(self, disableMotorsAndHeater=True):
		"""
		 Cancel the current printjob.
		"""
		if not super(PrinterS3g, self).cancelPrint():
			return

		self._printJob.cancel()

	# ~~~ Internal Callbacks ~~~~

	def printJobCancelled(self):
		# reset progress, height, print time
		self._setCurrentZ(None)
		self._setProgressData(None, None, None, None, None)

		# mark print as failure
		if self._currentFile is not None:
			self._fileManager.printFailed(self._currentFile["filename"], self.getPrintTime())
			self.unselectFile()
