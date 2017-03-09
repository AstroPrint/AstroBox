# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import serial
import threading

from sys import platform

from collections import deque

from octoprint.settings import settings

class CommsListener(object):
	# ~~~~~~~~~~
	# Implment these functions in the children class to respond to the events
	# ~~~~~~~~~~

	#
	# Called when the link has been opened
	#
	def onLinkOpened(self, link):
		pass

	#
	# Called when the link has an error
	#
	def onLinkError(self, error):
		pass

	#
	# Called when the link has been closed
	#
	def onLinkClosed(self):
		pass

	#
	# Called when a new command is received from the printer
	#
	def onCommandReceived(self):
		pass

	#
	# Called when a new command is needed from the file. Should return the command
	#
	def readNextCommand(self):
		pass

class ReaderListener(object):
	def onCommandReceived(self, command):
		pass

	def onReadError(self, error):
		pass

class CommandsComms(ReaderListener):

	def __init__(self, listener):
		self._listener = listener
		self._logger = logging.getLogger(self.__class__.__name__)
		self._serialLogger = logging.getLogger("SERIAL")
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)
		self._settings = settings()
		self._pendingCommandsQ = deque()
		self._historyQ = deque([], 100)

		self._link = None
		self._linkReader = None
		self._port = None
		self._baudrate = None

	def __del__(self):
		self._logger.debug('Object Removed')
		self.closeLink()

	#
	# returns an object representing the ports with devices connected in the following format
	#
	# { port: product_name }
	#
	def listPorts(self):
		import serial.tools.list_ports

		from usbid.device import device_list

		ports = {}

		for p in serial.tools.list_ports.comports():
			if p.description != 'n/a':
				ports[p.device] = p

		return ports

	#
	# Opens the serial port
	#
	# - port (string): the port to open
	# - baudrate (integer): the baudrate to use (optional)
	#
	# Returns (boolean): True is succesful or False if not
	#
	def openLink(self, port, baudrate= 115200):
		if self.isLinkOpen:
			self._logger.warn("The serial link was already opened")
			return True

		self._serialLoggerEnabled and self._serialLogger.debug("Connecting to: %s" % port)
		try:
			self._link = serial.Serial(port, baudrate, timeout=self._settings.getFloat(["serial", "timeout", "connection"]), writeTimeout=10000, rtscts=self._settings.getBoolean(["serial", "rtsctsFlowControl"]), dsrdtr=self._settings.getBoolean(["serial", "dsrdtrFlowControl"]), xonxoff=self._settings.getBoolean(["serial", "swFlowControl"]))

		except Exception as e:
			self._logger.error("Unexpected error while opening serial port: %s %s" % (port, e))
			self._listener.onLinkError("Failed to open serial port")
			return False

		if self._link:
			self._port = port
			self._baudrate = baudrate
			self._linkReader = LinkReader(self._link, self)
			self._linkReader.start()
			self._serialLoggerEnabled and self._serialLogger.info("Connected to: %s" % self._link)
			self._listener.onLinkOpened(self)
			return True

		else:
			self._logger.error("Unable to open serial port %s at %d" % (port, baudrate))
			self._listener.onLinkError("Failed to open serial port")
			return False

	#
	# Closes the serial port
	#
	def closeLink(self):
		if self.isLinkOpen:
			try:
				self._linkReader.stop()
				self._link.close()
				self._link = None

				#This can be sometimes called from the _linkReader thread.
				if self._linkReader != threading.current_thread():
					self._linkReader.join()

				self._linkReader = None
				self._port = None
				self._baudrate = None


				self._listener.onLinkClosed()

			except OSError as e:
				#log it but continue
				self._logger.error('Error closing serial port: %s' % e)

		self._link = None

	#
	# Whether the link is open or not
	#
	@property
	def isLinkOpen(self):
		return self._link and self._link.is_open

	#
	# Return the settings of the active connection. (port, baudrate)
	#
	@property
	def connectionSettings(self):
		return self._port, self._baudrate

	def serialLoggingChanged(self):
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)

	def writeOnLink(self, data):
		self._link.write(data)
		self._serialLoggerEnabled and self._serialLogger.debug('<<< %s' % data)

	def queueCommand(self, command):
		raise NotImplementedError()

	def startPrint(self, filename):
		raise NotImplementedError()

	def stopPrint(self):
		raise NotImplementedError()

	# ~~~~~~~~~~~~~~~~
	# ReaderListener ~
	# ~~~~~~~~~~~~~~~~

	def onCommandReceived(self, command):
		self._serialLoggerEnabled and self._serialLogger.debug('>> %s' % command)
		self._listener.onCommandReceived(command)

	def onReadError(self, error):
		self.closeLink()
		self._listener.onLinkError(error)

class LinkReader(threading.Thread):
	def __init__(self, link, listener):
		super(LinkReader, self).__init__()
		self._stopped = False
		self._listener = listener
		self._link = link

	def run(self):
		while not self._stopped:
			try:
				line = self._link.readline()
			except:
				line = None

			if not self._stopped:
				if line is None:
					self._listener.onReadError('Invalid Link')
					self.stop()
				else:
					self._listener.onCommandReceived(line.strip())

	def stop(self):
		self._stopped = True
