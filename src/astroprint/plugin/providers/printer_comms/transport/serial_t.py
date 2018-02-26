# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import serial
import logging
import threading
import re
import serial.tools.list_ports
import time

from sys import platform
from octoprint.settings import settings

from . import PrinterCommTransport

#
# Main class for Serial Link Transport
#

class SerialCommTransport(PrinterCommTransport):

	def __init__(self, eventListener):
		super(SerialCommTransport, self).__init__(eventListener)

		self._logger = logging.getLogger(self.__class__.__name__)
		self._serialLogger = logging.getLogger("SERIAL")
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)
		self._settings = settings()
		self._link = None
		self._linkReader = None
		self._port = None
		self._baudrate = None

	def listAvailablePorts(self):
		ports = {}
		if "linux" in platform:
			#https://rfc1149.net/blog/2013/03/05/what-is-the-difference-between-devttyusbx-and-devttyacmx/
			regex = re.compile(r"\/dev\/tty(?:ACM|USB|)[0-9]+")

		elif platform == "darwin":
			regex = re.compile(r"\/dev\/cu\.usb(?:serial|modem)[\w-]+")

		for p in serial.tools.list_ports.comports():
			if regex.match(p.device) is not None:
				ports[p.device] = p.product or "Unknown serial device"

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

		if not port:
			self._logger.error("Port not specified")
			return False

		self._serialLoggerEnabled and self._serialLogger.debug("Connecting to: %s" % port)
		try:
			self._link = serial.Serial(port, baudrate, timeout=self._settings.getFloat(["serial", "timeout", "connection"]), writeTimeout=10000, rtscts=self._settings.getBoolean(["serial", "rtsctsFlowControl"]), dsrdtr=self._settings.getBoolean(["serial", "dsrdtrFlowControl"]), xonxoff=self._settings.getBoolean(["serial", "swFlowControl"]))

		except Exception as e:
			self._logger.error("Unexpected error while opening serial port: %s %s" % (port, e))
			self._eventListener.onLinkError("failed_to_open", e)
			self._link = None
			return False

		if self._link:
			self._port = port
			self._baudrate = baudrate
			self._linkReader = LinkReader(self._link, self._eventListener)
			self._linkReader.start()
			self._serialLoggerEnabled and self._serialLogger.info("Connected to: %s" % self._link)
			self._eventListener.onLinkOpened()
			return True

		else:
			self._logger.error("Unable to open serial port %s at %d" % (port, baudrate))
			self._eventListener.onLinkError("failed_to_open", "No link")
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

				self._eventListener.onLinkClosed()

			except OSError as e:
				#log it but continue
				self._logger.error('Error closing serial port: %s' % e)

		self._link = None

	def write(self, data, completed= None):
		retriesLeft = 5
		while True:
			try:
				if self._link:
					self._link.write(data)
					if completed:
						completed()

				else:
					self._logger.error("Link has gone away")

				break

			except serial.SerialTimeoutException:
				retriesLeft -= 1

				if retriesLeft == 0:
					self._serialLoggerEnabled and self._serialLogger.info("No more retries left. Closing the connection")
					self._eventListener.onLinkError('unable_to_send', "Line returned nothing")
					break

				else:
					self._serialLoggerEnabled and self._serialLogger.info("Serial Timeout while sending data. Retries left: %d" % retriesLeft)
					time.sleep(0.5)

			except Exception as e:
				self._serialLoggerEnabled and self._serialLogger.info("Unexpected error while writing serial port: %s" % e)
				self._eventListener.onLinkError('unable_to_send', str(e))
				break

	@property
	def isLinkOpen(self):
		return self._link and self._link.is_open

	@property
	def canTransmit(self):
		return self.isLinkOpen

	@property
	def connSettings(self):
		return self._port, self._baudrate

#
# Class to read from serial port
#

class LinkReader(threading.Thread):
	def __init__(self, link, eventListener):
		super(LinkReader, self).__init__()
		self._stopped = False
		self._eventListener = eventListener
		self._link = link

	def run(self):
		while not self._stopped:
			try:
				line = self._link.readline()
			except:
				line = None

			if not self._stopped:
				if line is None:
					self._eventListener.onLinkError('invalid_link', "Line returned nothing")
					self.stop()
				else:
					if line is '':
						self._eventListener.onLinkInfo('timeout')
					else:
						self._eventListener.onDataReceived(line)

	def stop(self):
		self._stopped = True
