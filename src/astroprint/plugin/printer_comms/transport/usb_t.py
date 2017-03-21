# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import usb1
import logging

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
	def openLink(self, port_id):
		if port_id is not None:
			if self._dev_handle is None:
				port_parts = port_id.split(':') #port id is "vid:pid"
				vid = int(port_parts[0])
				pid = int(port_parts[1])

				self._context = usb1.USBContext()
				self._dev_handle = self._context.openByVendorIDAndProductID(vid, pid, skip_on_error=True)
				self._dev_handle.claimInterface(0)
				self._port_id = port_id

			return self.isLinkOpen

		return False

	#
	# closes communication with the USB device
	#
	def closeLink(self):
		if self._dev_handle:
			self._dev_handle.close()
			self._context.close()
			self._dev_handle = None
			self._context = None
			self._port_id = None

	# ~~~~~~~ From PrinterCommTransport ~~~~~~~~~~

	def write(self, data):
		if self._dev_handle:
			self._dev_handle.bulkWrite(0x01, data, len(data))

	@property
	def isLinkOpen(self):
		return self._dev_handle is not None

	@property
	def connSettings(self):
		return self._port_id, None

