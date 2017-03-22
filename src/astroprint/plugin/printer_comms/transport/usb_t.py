# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import usb1
import logging
import threading

from . import PrinterCommTransport

class UsbCommTransport(PrinterCommTransport):
	def __init__(self, eventListener):
		super(UsbCommTransport, self).__init__(eventListener)

		self._logger = logging.getLogger(self.__class__.__name__)
		self._serialLogger = logging.getLogger("SERIAL")
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)

		self._dev_handle = None
		self._context = None
		self._port_id = None
		self._sendEP = None
		self._receiveEP = None
		self._linkReader = None

	#
	# returns an object representing the USB devices connected in the following format
	#
	# {
	# 	device_address: {
	#			vendor_id: Id of the vendor
	#			product_id: Id of the product
	#			product_name: Name of the product
	# 	}
	# }
	#
	def listAvailableDevices(self):
		ports = {}
		try:
			with usb1.USBContext() as context:
				for device in context.getDeviceIterator(skip_on_error=True):
					vid = device.getVendorID()
					pid = device.getProductID()
					port_id = "%d:%d" % (vid, pid)
					ports[port_id] = {
						'vendor_id': device.getVendorID(),
						'product_id': device.getProductID(),
						'product_name': device.getProduct()
					}
		except usb1.USBErrorPipe as e:
			self._logger.error("USB Error: %s", e)

		return ports

	#
	# Setup USB device to start sending receiving data
	#
	def openLink(self, port_id, sendEndpoint, receiveEndpoint):
		if port_id is not None:
			if self._dev_handle is None:
				port_parts = port_id.split(':') #port id is "vid:pid"
				vid = int(port_parts[0])
				pid = int(port_parts[1])

				self._context = usb1.USBContext()
				self._dev_handle = self._context.openByVendorIDAndProductID(vid, pid, skip_on_error=True)
				self._dev_handle.claimInterface(0)
				self._port_id = port_id
				self._sendEP = sendEndpoint
				self._receiveEP = receiveEndpoint
				self._linkReader = LinkReader(self._dev_handle, receiveEndpoint, self._eventListener)
				self._linkReader.start()
				self._serialLoggerEnabled and self._serialLogger.info("Connected to USB Device -> Vendor: 0x%04x, Product: 0x%04x" % (vid, pid))
				self._eventListener.onLinkOpened()

			return self.isLinkOpen

		return False

	#
	# closes communication with the USB device
	#
	def closeLink(self):
		if self._dev_handle:
			self._linkReader.stop()
			self._dev_handle.close()
			self._context.close()
			self._dev_handle = None
			self._context = None
			self._port_id = None

			self._eventListener.onLinkClosed()

	# ~~~~~~~ From PrinterCommTransport ~~~~~~~~~~

	def write(self, data):
		if self._dev_handle:
			self._dev_handle.claimInterface(0)
			self._dev_handle.bulkWrite(self._sendEP, data)

	@property
	def isLinkOpen(self):
		return self._dev_handle is not None

	@property
	def connSettings(self):
		return self._port_id, None

#
# Class to read from serial port
#

class LinkReader(threading.Thread):
	def __init__(self, devHandle, receiveEP, eventListener):
		super(LinkReader, self).__init__()
		self._stopped = False
		self._eventListener = eventListener
		self._devHandle = devHandle
		self._receiveEP = receiveEP

	def run(self):
		while not self._stopped:
			try:
				data = None
				data = self._devHandle.bulkRead(self._receiveEP, 4096, timeout=2000)
				data = data.decode('ascii').strip()

			except usb1.USBErrorTimeout:
				self._eventListener.onLinkInfo('timeout')
				continue

			except Exception as e:
				data = None

			if not self._stopped:
				if data is None:
					self._eventListener.onLinkError('invalid_link')
					self.stop()
				else:
					for line in data.split('\r\n'):
						self._eventListener.onDataReceived(line)

	def stop(self):
		self._stopped = True

