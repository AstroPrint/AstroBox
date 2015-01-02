# coding=utf-8
__author__ = "Daniel Arroyo. 3DaGogo, Inc <daniel@3dagogo.com>"
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
import pybonjour
import octoprint.util

from astroprint.variant import variantManager
from astroprint.network import networkManager
from astroprint.boxrouter import boxrouterManager

class DiscoveryManager(object):
	ssdp_multicast_addr = "239.255.255.250"
	ssdp_multicast_port = 1900

	def __init__(self):
		self.logger = logging.getLogger(__name__)

		self.variantMgr = variantManager()
		self.networkMgr = networkManager()
		self.boxrouterMgr = boxrouterManager()

		# zeroconf
		self._sd_refs = dict()
		self._cnames = dict()

		# upnp/ssdp
		self._ssdp_monitor_active = False
		self._ssdp_monitor_thread = None
		self._ssdp_notify_timeout = 10
		self._ssdp_last_notify = 0

		#Zeroconf and SSDP services upon startup

		self.host = "%s.local" % self.get_instance_name()
		self.port = 80

		# Zeroconf
		self.zeroconf_register("_http._tcp", self.get_instance_name(), txt_record=self._create_http_txt_record_dict())
		self.zeroconf_register("_astroprint._tcp", self.get_instance_name(), txt_record=self._create_astroprint_txt_record_dict())

		# SSDP
		self._ssdp_register()

	# unregistering Zeroconf and SSDP service upon application shutdown

	def __del__(self):
		for key in self._sd_refs:
			reg_type, port = key
			self.zeroconf_unregister(reg_type, port)

		self._ssdp_unregister()

	##~~ helpers

	def get_instance_name(self):
		return self.networkMgr.getHostname()

	def get_uuid(self):
		return self.boxrouterMgr.boxId

	# ZeroConf

	def zeroconf_register(self, reg_type, name=None, port=None, txt_record=None):
		"""
		Registers a new service with Zeroconf/Bonjour/Avahi.

		:param reg_type: type of service to register, e.g. "_gntp._tcp"
		:param name: displayable name of the service, if not given defaults to the AstroPrint instance name
		:param port: port to register for the service, if not given defaults to AstroPrint's (public) port
		:param txt_record: optional txt record to attach to the service, dictionary of key-value-pairs
		"""

		if not name:
			name = self.get_instance_name()
		if not port:
			port = self.port

		params = dict(
			name=name,
			regtype=reg_type,
			port=port
		)
		if txt_record:
			params["txtRecord"] = pybonjour.TXTRecord(txt_record)

		key = (reg_type, port)
		self._sd_refs[key] = pybonjour.DNSServiceRegister(**params)
		self.logger.info(u"Registered {name} for {reg_type}".format(**locals()))

	def zeroconf_unregister(self, reg_type, port=None):
		"""
		Unregisteres a previously registered Zeroconf/Bonjour/Avahi service identified by service and port.

		:param reg_type: the type of the service to be unregistered
		:param port: the port of the service to be unregistered, defaults to AstroPrint's (public) port if not given
		:return:
		"""

		if not port:
			port = self.port

		key = (reg_type, port)
		if not key in self._sd_refs:
			return

		sd_ref = self._sd_refs[key]
		try:
			sd_ref.close()
			self.logger.debug("Unregistered {reg_type} on port {port}".format(reg_type=reg_type, port=port))
		except:
			self.logger.exception("Could not unregister {reg_type} on port {port}".format(reg_type=reg_type, port=port))

	# Zeroconf

	def _create_http_txt_record_dict(self):
		"""
		Creates a TXT record for the _http._tcp Zeroconf service supplied by this AstroPrint instance.

		Defines the keys for _http._tcp as defined in http://www.dns-sd.org/txtrecords.html

		:return: a dictionary containing the defined key-value-pairs, ready to be turned into a TXT record
		"""

		entries = dict(
			path="http://%s.local/" % self.get_instance_name()
		)

		return entries

	def _create_astroprint_txt_record_dict(self):
		"""
		Creates a TXT record for the _astroprint._tcp Zeroconf service supplied by this Astroprint instance.

		The following keys are defined:

		  * `path`: path prefix to actual AstroPrint instance, inherited from _http._tcp
		  * `version`: AstroPrint software version
		  * `model`: Model of the device that is running AstroPrint

		:return: a dictionary containing the defined key-value-pairs, ready to be turned into a TXT record
		"""

		entries = self._create_http_txt_record_dict()

		import octoprint.server

		entries.update(dict(
			version=octoprint.server.VERSION
			))

		modelName = self.variantMgr.data.get('productName')
		if modelName:
			entries.update(dict(model=modelName))

		return entries

	# SSDP/UPNP

	def getDiscoveryXmlContents(self):
		modelName = self.variantMgr.data.get('productName')
		vendor = "AstroPrint(R)"
		vendorUrl = "https://www.astroprint.com/"

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
        <modelDescription>{modelDescription}</modelDescription>
        <modelNumber>{modelNumber}</modelNumber>
       	<modelURL>{modelUrl}</modelURL>
        <serialNumber>{serialNumber}</serialNumber>
        <UDN>uuid:{uuid}</UDN>
        <serviceList>
        </serviceList>
        <presentationURL>{presentationUrl}</presentationURL>
    </device>
</root>""".format(
	friendlyName=self.get_instance_name(),
	manufacturer=vendor,
	manufacturerUrl=vendorUrl,
	modelName=modelName,
	modelDescription="",
	modelNumber="",
	modelUrl="",
	serialNumber=self.get_uuid(),
	uuid=self.get_uuid(),
	presentationUrl=flask.url_for("index", _external=True)
)	

	def _ssdp_register(self):
		"""
		Registers the AstroPrint instance as basic service with a presentation URL pointing to the web interface
		"""

		import threading

		self._ssdp_monitor_active = True

		self._ssdp_monitor_thread = threading.Thread(target=self._ssdp_monitor, kwargs=dict(timeout=self._ssdp_notify_timeout))
		self._ssdp_monitor_thread.daemon = True
		self._ssdp_monitor_thread.start()

	def _ssdp_unregister(self):
		"""
		Unregisters the AstroPrint instance again
		"""

		self._ssdp_monitor_active = False
		if self.host and self.port:
			for _ in xrange(2):
				self._ssdp_notify(alive=False)

	def _ssdp_notify(self, alive=True):
		"""
		Sends an SSDP notify message across the connected networks.

		:param alive: True to send an "ssdp:alive" message, False to send an "ssdp:byebye" message
		"""

		import socket
		import time

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

