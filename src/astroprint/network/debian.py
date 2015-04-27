# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import netifaces
import sarge
import os
import threading
import gobject

gobject.threads_init()

#This needs to happen before importing NetworkManager
from dbus.mainloop.glib import DBusGMainLoop, threads_init

DBusGMainLoop(set_as_default=True)

import NetworkManager

threads_init()

from dbus.exceptions import DBusException

from astroprint.network import NetworkManager as NetworkManagerBase

logger = logging.getLogger(__name__)

from tempfile import mkstemp
from shutil import move
from os import remove, close

from octoprint.server import eventManager
from octoprint.events import Events

class NetworkManagerEvents(threading.Thread):
	def __init__(self, manager):
		super(NetworkManagerEvents, self).__init__()
		self.daemon = True
		self._manager = manager
		self._online = None
		self._currentIpv4Address = None
		self._activeDevice = None

		self._propertiesListener = NetworkManager.NetworkManager.connect_to_signal('PropertiesChanged', self.propertiesChanged)
		self._stateChangeListener = NetworkManager.NetworkManager.connect_to_signal('StateChanged', self.globalStateChanged)
		self._devicePropertiesListener = None
		self._monitorActivatingListener = None

		logger.info('Looking for Active Connections...')
		d = self.getActiveConnectionDevice()
		if d:
			self._devicePropertiesListener = d.Dhcp4Config.connect_to_signal('PropertiesChanged', self.activeDeviceConfigChanged)
			self._currentIpv4Address = d.Ip4Address
			self._activeDevice = d
			self._online = True
			logger.info('Active Connection found at %s (%s)' % (d.IpInterface, d.Ip4Address))

	def __del__(self):
		self._propertiesListener.remove()
		self._stateChangeListener.remove()

	def getActiveConnectionDevice(self):
		connections = NetworkManager.NetworkManager.ActiveConnections
		for c in connections:
			if c.State == NetworkManager.NM_ACTIVE_CONNECTION_STATE_ACTIVATED and c.Default:
				d = c.Devices[0]
				return d

		return None		

	def run(self):
		gobject.idle_add(logger.info, 'NetworkManagerEvents is listening for signals')
		gobject.MainLoop().run()

	def globalStateChanged(self, state):
		#uncomment for debugging only
		#gobject.idle_add(logger.info, 'globalStateChanged, new(%s)' % NetworkManager.const('state', state))
		if not self._online and state == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
			self._setOnline(True)

	def propertiesChanged(self, properties):
		if self._online:
			if "ActiveConnections" in properties and len(properties['ActiveConnections']) == 0:
				self._setOnline(False)

		else:
			if "State" in properties and properties["State"] == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
				self._setOnline(True)

			elif "ActiveConnections" in properties and len(properties['ActiveConnections']) > 0:
				for c in properties['ActiveConnections']:
					if c.State == NetworkManager.NM_ACTIVE_CONNECTION_STATE_ACTIVATING:
						if self._monitorActivatingListener:
							self._monitorActivatingListener.remove()

						self._monitorActivatingListener = c.connect_to_signal('PropertiesChanged', self.monitorActivatingConnection)

	def monitorActivatingConnection(self, properties):
		if "State" in properties and properties['State'] == NetworkManager.NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
			if self._monitorActivatingListener:
				self._monitorActivatingListener.remove()
				self._monitorActivatingListener = None

			self._setOnline(True)

	def activeDeviceConfigChanged(self, properties):
		if "Options" in properties and "ip_address" in properties["Options"] and properties["Options"]["ip_address"] != self._currentIpv4Address:
			self._currentIpv4Address = properties["Options"]["ip_address"]
			self._setOnline(True)
			gobject.idle_add(eventManager.fire, Events.NETWORK_IP_CHANGED, self._currentIpv4Address)

	def _setOnline(self, value):
		if value == self._online:
			return

		if value:
			d = self.getActiveConnectionDevice()

			if d:
				if self._activeDevice:
					self._currentIpv4Address = self._activeDevice.Ip4Address

				self._activeDevice = d
				if self._devicePropertiesListener:
					self._devicePropertiesListener.remove()

				self._devicePropertiesListener = d.Dhcp4Config.connect_to_signal('PropertiesChanged', self.activeDeviceConfigChanged)
				gobject.idle_add(logger.info, 'Active Connection changed to %s (%s)' % (d.IpInterface, self._currentIpv4Address))

				self._online = True
				gobject.idle_add(eventManager.fire, Events.NETWORK_STATUS, 'online')

		else:
			self._online = False
			self._currentIpv4Address = None
			gobject.idle_add(eventManager.fire, Events.NETWORK_STATUS, 'offline')
			if self._manager.isHotspotActive() is False: #isHotspotActive returns None if not possible
				gobject.idle_add(logger.info, 'AstroBox is offline. Starting hotspot...')
				result = self._manager.startHotspot() 
				if result is True:
					gobject.idle_add(logger.info, 'Hostspot started.')
				else:
					gobject.idle_add(logger.error, 'Failed to start hostspot: %s' % result)


class DebianNetworkManager(NetworkManagerBase):
	def __init__(self):
		super(DebianNetworkManager, self).__init__()
		self._nm = NetworkManager
		self._eventListener = NetworkManagerEvents(self)
		self._eventListener.start()

		if not self.settings.getBoolean(['wifi', 'hotspotOnlyOffline']):
			self.startHotspot()

	def conectionStatus(self):
		return self._nm.const('state', self._nm.NetworkManager.status())

	def getWifiNetworks(self):
		wifiDevice = self.getWifiDevice()

		networks = {}

		if wifiDevice:
			for ap in wifiDevice.SpecificDevice().GetAccessPoints():
				signal = ord(ap.Strength)
				ssid = ap.Ssid

				if ap.Ssid not in networks or signal > networks[ssid]['signal']:
					networks[ssid] = {
						'id': ap.HwAddress,
						'signal': signal,
						'name': ssid,
						'secured': True if ap.WpaFlags or ap.RsnFlags else False
					}

			return [v for k,v in networks.iteritems()]

		return None

	def getActiveConnections(self):
		activeConnections = { 'wired': None, 'wireless': None, 'manual': None}

		if self._nm.NetworkManager.State == self._nm.NM_STATE_CONNECTED_GLOBAL:
			connections = self._nm.NetworkManager.ActiveConnections
			for c in connections:
				if c.State == self._nm.NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
					d = c.Devices[0]

					if d.DeviceType == self._nm.NM_DEVICE_TYPE_ETHERNET:
						if not activeConnections['wired']:
							activeConnections['wired'] = {
								'id': d.SpecificDevice().HwAddress,
								'ip': d.Ip4Address
							}

					elif d.DeviceType == self._nm.NM_DEVICE_TYPE_WIFI:
						if not activeConnections['wireless']:
							ap = c.SpecificObject
							activeConnections['wireless'] = {
								'id': ap.HwAddress,
								'signal': ord(ap.Strength),
								'name': ap.Ssid,
								'ip': d.Ip4Address,
								'secured': True if ap.WpaFlags or ap.RsnFlags else False
							}

		return activeConnections

	def getWifiDevice(self):
		devices = self._nm.NetworkManager.GetDevices()
		for d in devices:
			if d.DeviceType == self._nm.NM_DEVICE_TYPE_WIFI:
				return d

		return False

	def isHotspotable(self):
		return bool(self.settings.get(['wifi', 'hotspotDevice'])) and self.isHotspotActive() != None

	def isOnline(self):
		return self._eventListener._online

	def setWifiNetwork(self, bssid, password = None):
		wifiDevice = self.getWifiDevice()

		if bssid and wifiDevice:
			accessPoint = None

			for ap in wifiDevice.SpecificDevice().GetAccessPoints():
				if ap.HwAddress == bssid:
					accessPoint = ap
					break

			if accessPoint:
				ssid = accessPoint.Ssid
				connection = None
				for c in self._nm.Settings.ListConnections():
					if c.GetSettings()['connection']['id'] == ssid:
						connection = c
						break

				try:
					if connection:
						self._nm.NetworkManager.ActivateConnection(connection, wifiDevice, "/")
					else:
						options = {
							'connection': {
								'id': ssid
							}
						}

						if password:
							options['802-11-wireless-security'] = {
								'psk': password
							}

						(connection, activeConnection) = self._nm.NetworkManager.AddAndActivateConnection(options, wifiDevice, accessPoint)

				except DBusException as e:
					if e.get_dbus_name() == 'org.freedesktop.NetworkManager.InvalidProperty' and e.get_dbus_message() == 'psk':
						return {'message': 'Invalid Password'}
					else:
						raise

				import gobject
				loop = gobject.MainLoop()

				result = {}

				def connectionStateChange(new_state, old_state, reason):
					if new_state == self._nm.NM_DEVICE_STATE_ACTIVATED:
						result['id'] = accessPoint.HwAddress
						result['signal'] = ord(accessPoint.Strength)
						result['name'] = accessPoint.Ssid
						result['ip'] = wifiDevice.Ip4Address
						result['secured'] = True if accessPoint.WpaFlags or accessPoint.RsnFlags else False
						loop.quit()
					elif new_state == self._nm.NM_DEVICE_STATE_FAILED:
						connection.Delete()
						result['message'] = "The connection could not be created"
						loop.quit()

				wifiDevice.connect_to_signal('StateChanged', connectionStateChange)

				loop.run()

				return result

		return None

	def forgetWifiNetworks(self):
		conns = self._nm.Settings.ListConnections()

		if not self.isHotspotActive():
			self.startHotspot()

		for c in conns:
			settings = c.GetSettings()
			if '802-11-wireless' in settings:
				logger.info('Deleting connection %s' % settings['802-11-wireless']['ssid'])
				c.Delete()

	def isHotspotActive(self):
		interface = self.settings.get(['wifi', 'hotspotDevice'])

		if interface:
			try:
				info = netifaces.ifaddresses(interface)

			except ValueError:
				logger.warn("Hotspot interface (%s) is not valid in this system." % interface)

			else:
				return netifaces.AF_INET in info

		return None

	def startHotspot(self):
		if self.isHotspotActive():
			return True

		try:
			p = sarge.run("service wifi_access_point start", stderr=sarge.Capture())
			if p.returncode != 0:
				returncode = p.returncode
				stderr_text = p.stderr.text
				logger.warn("Start hotspot failed with return code %i: %s" % (returncode, stderr_text))
				return "Start hotspot failed with return code %i: %s" % (returncode, stderr_text)
			else:
				return True

		except Exception, e:
			logger.warn("Start hotspot failed with return code: %s" % e)
			return "Start hotspot failed with return code: %s" % e

	def stopHotspot(self):
		try:
			p = sarge.run("service wifi_access_point stop", stderr=sarge.Capture())
			if p.returncode != 0:
				returncode = p.returncode
				stderr_text = p.stderr.text
				logger.warn("Stop hotspot failed with return code %i: %s" % (returncode, stderr_text))
				return "Stop hotspot failed with return code %i: %s" % (returncode, stderr_text)
			else:
				return True

		except Exception, e:
			logger.warn("Stop hotspot failed with return code: %s" % e)
			return "Stop hotspot failed with return code: %s" % e

	def getHostname(self):
		return self._nm.Settings.Hostname

	def setHostname(self, name):
		settings = self._nm.Settings

		old_name = settings.Hostname

		settings.SaveHostname(name)

		if (settings.Hostname == name):
			def replace(file_path, pattern, subst):
				#Create temp file
				fh, abs_path = mkstemp()
				new_file = open(abs_path,'w')
				old_file = open(file_path)
				for line in old_file:
					new_file.write(line.replace(pattern, subst))
				#close temp file
				new_file.close()
				close(fh)
				old_file.close()
				#Remove original file
				remove(file_path)
				#Move new file
				move(abs_path, file_path)
			
			udpateFiles = [
				'/etc/hosts'
			]

			for f in udpateFiles:
				if (os.path.exists(f) and os.path.isfile(f)):
					replace(f, old_name, name)

			return True

		else:
			return False
