# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import usb1
import libusb1
import logging
import threading
import time

from collections import deque

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
		self._hasError = False
		#self._incomingQueue = None
		self._writeTransfers = []
		self._writeLock = threading.Lock()

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

		except usb1.USBErrorIO:
			self._logger.error("USB Link can't be opened")

		return ports

	#
	# Setup USB device to start sending receiving data
	#
	def openLink(self, port_id, sendEndpoint, receiveEndpoint):
		if port_id is not None:
			if self._dev_handle is None:
				try:
					port_parts = port_id.split(':') #port id is "vid:pid"
					vid = int(port_parts[0])
					pid = int(port_parts[1])

					self._context = usb1.USBContext()
					self._dev_handle = self._context.openByVendorIDAndProductID(vid, pid, skip_on_error=True)
					if self._dev_handle is not None:
						self._hasError = False
						self._dev_handle.claimInterface(0)
						self._port_id = port_id
						self._sendEP = sendEndpoint
						self._receiveEP = receiveEndpoint
						#self._incomingQueue = IncomingQueue(self._eventListener)
						#self._incomingQueue.start()
						#self._linkReader = LinkReader(self._dev_handle, self._context, receiveEndpoint, self._eventListener, self._incomingQueue, self)
						self._linkReader = LinkReader(self._dev_handle, self._context, receiveEndpoint, self._eventListener, self)
						self._linkReader.start()
						self._serialLoggerEnabled and self._serialLogger.debug("Connected to USB Device -> Vendor: 0x%04x, Product: 0x%04x" % (vid, pid))
						self._eventListener.onLinkOpened()
						return True

				except usb1.USBErrorBusy:
					return False

			else:
				return True #It was already opened

		return False

	#
	# closes communication with the USB device
	#
	def closeLink(self):
		if self._dev_handle:

			for t in self._writeTransfers:
				try:
					t.cancel()
				except usb1.USBErrorNotFound:
					pass

			self._writeTransfers = []

			if self._linkReader:
				self._linkReader.stop()
				self._linkReader = None

			#if self._incomingQueue:
			#	self._incomingQueue.stop()
			#	self._incomingQueue = None

			try:
				self._dev_handle.releaseInterface(0)
			except ( usb1.USBErrorNoDevice, usb1.USBErrorNotFound):
				pass

			self._dev_handle = None
			self._context = None
			self._port_id = None

			self._eventListener.onLinkClosed()
			self._serialLoggerEnabled and self._serialLogger.debug("(X) Link Closed")

	# ~~~~~~~ From PrinterCommTransport ~~~~~~~~~~

	def write(self, data, completed= None):
		if self._dev_handle:
			with self._writeLock:
				transfer = None
				for t in self._writeTransfers:
					if not t.isSubmitted():
						transfer = t
						break

				if transfer:
					transfer.setBuffer(data)
					transfer.setUserData(completed)
					transfer.submit()

				else:
					transfer = self._dev_handle.getTransfer()
					transfer.setBulk(
						self._sendEP,
						data,
						callback= self._processWrite,
						user_data= completed
					)
					self._writeTransfers.append(transfer)
					transfer.submit()

	@property
	def isLinkOpen(self):
		return self._dev_handle is not None

	@property
	def canTransmit(self):
		return not self._hasError

	@property
	def connSettings(self):
		return self._port_id, None

	#
	# private
	#
	def _processWrite(self, transfer):
		status = transfer.getStatus()
		if status == usb1.TRANSFER_COMPLETED:
			completed = transfer.getUserData()
			if completed:
				completed()

		elif status == usb1.TRANSFER_TIMED_OUT:
			transfer.submit()

			try:
				self._eventListener.onLinkInfo('write_timeout')
			except Exception as e:
				self._logger.error('Error sending timeout: %s' % e, exc_info=True)

		elif status == usb1.TRANSFER_STALL:
			try:
				self._dev_handle.clearHalt(self._sendEP)
				transfer.submit()
			except usb1.USBErrorOther as e:
				self._eventListener.onLinkError('usb_error', "sender error while clearing Halt: %s" % e)

		else:
			self._eventListener.onLinkError('usb_error', "sender error: %s" % libusb1.libusb_transfer_status(status))

#
# Class to read from serial port
#

class LinkReader(threading.Thread):
	#def __init__(self, devHandle, context, receiveEP, eventListener, incomingQueue, transport):
	def __init__(self, devHandle, context, receiveEP, eventListener, transport):
		super(LinkReader, self).__init__()
		self._stopped = False
		self._eventListener = eventListener
		self._devHandle = devHandle
		self._receiveEP = receiveEP
		self._transport = transport
		#self._incomingQueue = incomingQueue
		self._context = context
		self._logger = logging.getLogger(self.__class__.__name__)
		self._transferList = []

	def run(self):
		for _ in xrange(5):
			transfer = self._devHandle.getTransfer()
			transfer.setBulk(
				self._receiveEP,
				4096,
				callback=self.processReceivedData,
			)
			transfer.submit()
			self._transferList.append(transfer)

		while any(x.isSubmitted() for x in self._transferList) and not self._stopped:
			try:
				self._context.handleEvents()
			except usb1.USBErrorInterrupted:
				pass

	def processReceivedData(self, transfer):
		status = transfer.getStatus()
		if status == usb1.TRANSFER_COMPLETED:
			data = transfer.getBuffer()[:transfer.getActualLength()]
			transfer.submit()
			if data:
				#self._incomingQueue.addResponse(data)
				try:
					self._eventListener.onDataReceived(data)
				except Exception as e:
					self._logger.error('Error processing received data [%r]: %s' % (data, e), exc_info=True)

		elif status == usb1.TRANSFER_TIMED_OUT:
			transfer.submit()

			try:
				self._eventListener.onLinkInfo('read_timeout')
			except Exception as e:
				self._logger.error('Error sending timeout: %s' % e, exc_info=True)

		elif status == usb1.TRANSFER_STALL:
			try:
				self._devHandle.clearHalt(self._receiveEP)
				transfer.submit()
			except usb1.USBErrorOther as e:
				self._eventListener.onLinkError('usb_error', "receiver error clearing Halt: %s" % e)

		elif not self._stopped:
			self._eventListener.onLinkError('usb_error', "receiver error: %s" % libusb1.libusb_transfer_status(status))

	def stop(self):
		self._stopped = True

		for x in self._transferList:
			if x.isSubmitted():
				try:
					x.cancel()
				except ( usb1.USBErrorNotFound, usb1.USBErrorNoDevice ):
					pass

#
# Class to queue incoming commands
#

'''class IncomingQueue(threading.Thread):
	def __init__(self, eventListener):
		super(IncomingQueue, self).__init__()
		self._stopped = False
		self._reportResponse = threading.Event()
		self._eventListener = eventListener
		self._queue = deque()

	def run(self):
		while not self._stopped:
			self._reportResponse.wait()
			if not self._stopped:
				try:
					response = self._queue.pop()
				except IndexError:
					self._reportResponse.clear()
					continue

				if response:
					try:
						self._eventListener.onDataReceived(response)
					except Exception as e:
						self._logger.error('Error processing received data [%r]: %s' % (data, e), exc_info=True)

	def addResponse(self, response):
		self._queue.appendleft(response)
		self._reportResponse.set()

	def stop(self):
		self._stopped = True
		self._reportResponse.set()'''
