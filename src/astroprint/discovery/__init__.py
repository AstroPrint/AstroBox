# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@astroprint.com>"
__copyright__ = "Copyright (C) 2015 3DaGoGo, Inc. - Released under terms of the AGPLv3 License"

"""
This is an adaptation of the Octoprint Discovery plugin: https://github.com/foosel/OctoPrint/blob/3d5fdf2a917833808f132212b76ad3c6c5768419/src/octoprint/plugins/discovery/__init__.py
"""

# singleton
_instance = None

def discoveryManager():
	global _instance
	if _instance is None:
		_instance = DiscoveryManager()

	return _instance

import logging
import os
import flask
import octoprint.util
import threading
import time

from octoprint.events import eventManager, Events

from astroprint.variant import variantManager
from astroprint.network.manager import networkManager
from astroprint.boxrouter import boxrouterManager
from astroprint.software import softwareManager

class DiscoveryManager(object):
	ssdp_multicast_addr = "239.255.255.250"
	ssdp_multicast_port = 1900

	def __init__(self):
		self._eventManager = eventManager()

		self.logger = logging.getLogger(__name__)

		self.variantMgr = variantManager()
		self.softwareMgr = softwareManager()

		# upnp/ssdp
		self._ssdp_monitor_active = False
		self._ssdp_monitor_thread = None
		self._ssdp_notify_timeout = 10
		self._ssdp_last_notify = 0
		self._ssdp_last_unregister = 0

		# SSDP
		if networkManager().isOnline():
			self._ssdp_register()

		self._eventManager.subscribe(Events.NETWORK_STATUS, self._onNetworkStateChanged)


	# unregistering SSDP service upon shutdown

	def __del__(self):
		self._ssdp_unregister()
		self._eventManager.unsubscribe(Events.NETWORK_STATUS, self._onNetworkStateChanged)

	##~~ helpers

	def get_instance_name(self):
		return networkManager().getHostname()

	def get_uuid(self):
		return boxrouterManager().boxId

	def _onNetworkStateChanged(self, event, state):
		if state == 'offline':
			self._ssdp_unregister()

		elif state == 'online':
			self._ssdp_register()

		else:
			self._logger.warn('Invalid network state (%s)' % state)

	# SSDP/UPNP

	def getDiscoveryXmlContents(self):
		modelName = self.variantMgr.data.get('productName')
		modelLink = self.variantMgr.data.get('productLink')
		modelDescription = "%s running on %s" % (self.softwareMgr.versionString, self.softwareMgr.platform)
		vendor = "AstroPrint"
		vendorUrl = "https://www.astroprint.com/"
		friendlyName = "%s (%s)" % (self.get_instance_name(), modelName)

		return """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
    <specVersion>
        <major>1</major>
        <minor>0</minor>
    </specVersion>
    <device>
        <deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
        <friendlyName>{friendlyName}</friendlyName>
        <manufacturer>{manufacturer}</manufacturer>
        <manufacturerURL>{manufacturerUrl}</manufacturerURL>
        <modelName>{modelName}</modelName>
        <modelNumber>{modelDescription}</modelNumber>
       	<modelURL>{modelUrl}</modelURL>
        <serialNumber>{serialNumber}</serialNumber>
        <UDN>uuid:{uuid}</UDN>
        <serviceList>
        </serviceList>
        <presentationURL>{presentationUrl}</presentationURL>
    </device>
</root>""".format(
	friendlyName=friendlyName,
	manufacturer=vendor,
	manufacturerUrl=vendorUrl,
	modelName=modelName,
	modelDescription=modelDescription,
	modelUrl=modelLink,
	serialNumber=self.get_uuid(),
	uuid=self.get_uuid(),
	presentationUrl=flask.url_for("index", _external=True)
)	

	def _ssdp_register(self):
		"""
		Registers the AstroPrint instance as basic service with a presentation URL pointing to the web interface
		"""

		time_since_last_unregister = time.time() - self._ssdp_last_unregister

		if time_since_last_unregister < ( self._ssdp_notify_timeout + 1 ):
			wait_seconds = ( self._ssdp_notify_timeout + 1) - time_since_last_unregister
			self.logger.info("Waiting %s seconds before starting SSDP Service..." % wait_seconds)
			time.sleep(wait_seconds)

			#Make sure that the network is still after the wait
			if not networkManager().isOnline():
				return

		self._ssdp_monitor_active = True

		self._ssdp_monitor_thread = threading.Thread(target=self._ssdp_monitor, kwargs=dict(timeout=self._ssdp_notify_timeout))
		self._ssdp_monitor_thread.daemon = True
		self._ssdp_monitor_thread.start()

	def _ssdp_unregister(self):
		"""
		Unregisters the AstroPrint instance again
		"""

		if self._ssdp_monitor_active:
			self._ssdp_monitor_active = False
			for _ in xrange(2):
				self._ssdp_notify(alive=False)

			self._ssdp_last_unregister = time.time()

	def _ssdp_notify(self, alive=True):
		"""
		Sends an SSDP notify message across the connected networks.

		:param alive: True to send an "ssdp:alive" message, False to send an "ssdp:byebye" message
		"""

		import socket

		if alive and self._ssdp_last_notify + self._ssdp_notify_timeout > time.time():
			# we just sent an alive, no need to send another one now
			return

		if alive and not self._ssdp_monitor_active:
			# the monitor already shut down, alive messages don't make sense anymore as byebye will shortly follow
			return

		for addr in octoprint.util.interface_addresses():
			try:
				sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
				sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
				sock.bind((addr, 0))

				location = "http://{addr}/discovery.xml".format(addr=addr)

				self.logger.debug("Sending NOTIFY {} via {}".format("alive" if alive else "byebye", addr))
				notify_message = "".join([
					"NOTIFY * HTTP/1.1\r\n",
					"Server: Python/2.7\r\n",
					"Cache-Control: max-age=900\r\n",
					"Location: {location}\r\n",
					"NTS: {nts}\r\n",
					"NT: upnp:rootdevice\r\n",
					"USN: uuid:{uuid}::upnp:rootdevice\r\n",
					"HOST: {mcast_addr}:{mcast_port}\r\n\r\n"
				])
				message = notify_message.format(uuid=self.get_uuid(),
				                                location=location,
				                                nts="ssdp:alive" if alive else "ssdp:byebye",
				                                mcast_addr=self.__class__.ssdp_multicast_addr,
				                                mcast_port=self.__class__.ssdp_multicast_port)
				for _ in xrange(2):
					# send twice, stuff might get lost, it's only UDP
					sock.sendto(message, (self.__class__.ssdp_multicast_addr, self.__class__.ssdp_multicast_port))
			except:
				pass

		self._ssdp_last_notify = time.time()

	def _ssdp_monitor(self, timeout=5):
		"""
		Monitor thread that listens on the multicast address for M-SEARCH requests and answers them if they are relevant

		:param timeout: timeout after which to stop waiting for M-SEARCHs for a short while in order to put out an
		                alive message
		"""

		from BaseHTTPServer import BaseHTTPRequestHandler
		from StringIO import StringIO
		import socket

		socket.setdefaulttimeout(timeout)

		location_message = "".join([
			"HTTP/1.1 200 OK\r\n",
			"ST: upnp:rootdevice\r\n",
			"USN: uuid:{uuid}::upnp:rootdevice\r\n",
			"Location: {location}\r\n",
			"Cache-Control: max-age=60\r\n\r\n"
		])

		class Request(BaseHTTPRequestHandler):

			def __init__(self, request_text):
				self.rfile = StringIO(request_text)
				self.raw_requestline = self.rfile.readline()
				self.error_code = self.error_message = None
				self.parse_request()

			def send_error(self, code, message=None):
				self.error_code = code
				self.error_message = message

		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
		sock.bind(('', self.__class__.ssdp_multicast_port))

		sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.__class__.ssdp_multicast_addr) + socket.inet_aton('0.0.0.0'))

		self.logger.info(u"Registered {} for SSDP".format(self.get_instance_name()))

		self._ssdp_notify(alive=True)

		try:
			while (self._ssdp_monitor_active):
				try:
					data, address = sock.recvfrom(4096)
					request = Request(data)
					if not request.error_code and request.command == "M-SEARCH" and request.path == "*" and (request.headers["ST"] == "upnp:rootdevice" or request.headers["ST"] == "ssdp:all") and request.headers["MAN"] == '"ssdp:discover"':
						interface_address = octoprint.util.address_for_client(*address)
						if not interface_address:
							self.logger.warn("Can't determine address to user for client {}, not sending a M-SEARCH reply".format(address))
							continue
						message = location_message.format(uuid=self.get_uuid(), location="http://{host}/discovery.xml".format(host=interface_address))
						sock.sendto(message, address)
						self.logger.debug("Sent M-SEARCH reply for {path} and {st} to {address!r}".format(path=request.path, st=request.headers["ST"], address=address))
				except socket.timeout:
					pass
				finally:
					self._ssdp_notify(alive=True)
		finally:
			try:
				sock.close()
			except:
				pass

