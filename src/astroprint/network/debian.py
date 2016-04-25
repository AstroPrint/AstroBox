# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import netifaces
import sarge
import os
import threading
import gobject
import time

gobject.threads_init()

#This needs to happen before importing NetworkManager
from dbus.mainloop.glib import DBusGMainLoop, threads_init

DBusGMainLoop(set_as_default=True)

import NetworkManager

from dbus.exceptions import DBusException

from astroprint.network import NetworkManager as NetworkManagerBase

logger = logging.getLogger(__name__)

from tempfile import mkstemp
from shutil import move
from os import remove, close

from octoprint.server import eventManager
from octoprint.events import Events

def idle_add_decorator(func):
    def callback(*args):
        gobject.idle_add(func, *args)
    return callback

class NetworkManagerEvents(threading.Thread):
	def __init__(self, manager):
		super(NetworkManagerEvents, self).__init__()
		self.daemon = True
		self._manager = manager
		self._online = None
		self._currentIpv4Address = None
		self._activeDevice = None
		self._activatingConnection = None
		self._setOnlineCondition = threading.Condition()

	def getActiveConnectionDevice(self):
		connections = NetworkManager.NetworkManager.ActiveConnections
		for c in connections:
			if c.State == NetworkManager.NM_ACTIVE_CONNECTION_STATE_ACTIVATED and c.Default:
				d = c.Devices[0]
				return d

		return None

	def run(self):
		self._stopped = False
		self._loop = gobject.MainLoop()

		self._propertiesListener = NetworkManager.NetworkManager.connect_to_signal('PropertiesChanged', self.propertiesChanged)
		self._stateChangeListener = NetworkManager.NetworkManager.connect_to_signal('StateChanged', self.globalStateChanged)
		self._devicePropertiesListener = None
		self._monitorActivatingListener = None

		logger.info('Looking for Active Connections...')
		if NetworkManager.NetworkManager.State == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
			self._setOnline(True)

		#d = self.getActiveConnectionDevice()
		#if d:
		#	self._devicePropertiesListener = d.Dhcp4Config.connect_to_signal('PropertiesChanged', self.activeDeviceConfigChanged)
		#	self._currentIpv4Address = d.Ip4Address
		#	self._activeDevice = d
		#	self._online = True
		#	logger.info('Active Connection found at %s (%s)' % (d.IpInterface, d.Ip4Address))

		while not self._stopped:
			try:
				self._loop.run()

			except DBusException as e:
				gobject.idle_add(logger.error, 'Exception during NetworkManagerEvents: %s' % e)
				self._stopped = True
				self._loop.quit()


	def stop(self):
		logger.info('NetworkManagerEvents stopping.')

		if self._propertiesListener:
			self._propertiesListener.remove()
			self._propertiesListener = None

		if self._stateChangeListener:
			self._stateChangeListener.remove()
			self._stateChangeListener = None

		if self._monitorActivatingListener:
			self._monitorActivatingListener.remove()
			self._monitorActivatingListener = None

		if self._devicePropertiesListener:
			self._devicePropertiesListener.remove()
			self._devicePropertiesListener = None

		self._stopped = True
		self._loop.quit()

	@idle_add_decorator
	def globalStateChanged(self, state):
		#uncomment for debugging only
		#logger.info('Network Global State Changed, new(%s)' % NetworkManager.const('state', state))
		if state == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
			self._setOnline(True)
		elif state != NetworkManager.NM_STATE_CONNECTING:
			self._setOnline(False)

	@idle_add_decorator
	def propertiesChanged(self, properties):
		if "ActiveConnections" in properties: 
			if len(properties['ActiveConnections']) == 0:
				self._setOnline(False)
				return

			elif not self._monitorActivatingListener:
				for c in properties['ActiveConnections']:
					if c.State == NetworkManager.NM_ACTIVE_CONNECTION_STATE_ACTIVATING:
						if self._monitorActivatingListener:
							self._monitorActivatingListener.remove()

						eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {'status': 'connecting'})

						self._activatingConnection = c.Connection
						self._monitorActivatingListener = c.Devices[0].connect_to_signal('StateChanged', self.monitorActivatingConnection)

						settings = c.Connection.GetSettings()
						if settings:
							logger.info('Activating Connection %s' % settings['connection']['id'])

						return

		if "State" in properties and properties["State"] == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
			self._setOnline(True)

	@idle_add_decorator
	def monitorActivatingConnection(self, new_state, old_state, reason):
		logger.info('Activating State Change %s -> %s' % (NetworkManager.const('device_state', old_state),NetworkManager.const('device_state', new_state)))
		if self._activatingConnection:
			if new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
				if self._monitorActivatingListener:
					self._monitorActivatingListener.remove()
					self._monitorActivatingListener = None

				d = self.getActiveConnectionDevice()
				if d.DeviceType == NetworkManager.NM_DEVICE_TYPE_ETHERNET:
					eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {
						'status': 'connected', 
						'info': {
							'type': 'ethernet',
							'ip': d.Ip4Address
						}
					})					
				else:
					ap = d.SpecificDevice().ActiveAccessPoint
					eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {
						'status': 'connected', 
						'info': {
							'type': 'wifi',
							'signal': ap.Strength,
							'name': ap.Ssid,
							'ip': d.Ip4Address
						}
					})

				self._activatingConnection = None
				self._setOnline(True)

			elif new_state in [NetworkManager.NM_DEVICE_STATE_FAILED, NetworkManager.NM_DEVICE_STATE_UNKNOWN]:
				logger.warn('Connection reached state %s, reason: %s' % (NetworkManager.const('device_state', new_state), NetworkManager.const('device_state_reason', reason) ) )
				eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {'status': 'failed', 'reason': NetworkManager.const('device_state_reason', reason)})
				# we should probably remove the connection
				self._activatingConnection.Delete()

			elif new_state == NetworkManager.NM_DEVICE_STATE_DISCONNECTED:
				if self._monitorActivatingListener:
					self._monitorActivatingListener.remove()
					self._monitorActivatingListener = None

				eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {'status': 'disconnected'})

				self._activatingConnection = None

				#check the global connection status before setting it to false
				if NetworkManager.NetworkManager.state() != NetworkManager.NM_STATE_CONNECTED_GLOBAL:
					self._setOnline(False)

	@idle_add_decorator
	def activeDeviceConfigChanged(self, properties):
		if "Options" in properties and "ip_address" in properties["Options"] and properties["Options"]["ip_address"] != self._currentIpv4Address:
			self._currentIpv4Address = properties["Options"]["ip_address"]
			self._setOnline(True)
			eventManager.fire(Events.NETWORK_IP_CHANGED, self._currentIpv4Address)

	def _setOnline(self, value):
		with self._setOnlineCondition:
			if value == self._online:
				return

			if value:
				d = self.getActiveConnectionDevice()

				if d:
					self._activeDevice = d
					if self._devicePropertiesListener:
						self._devicePropertiesListener.remove()

					if self._activeDevice:
						self._currentIpv4Address = self._activeDevice.Ip4Address

					self._devicePropertiesListener = d.Dhcp4Config.connect_to_signal('PropertiesChanged', self.activeDeviceConfigChanged)
					logger.info('Active Connection is now %s (%s)' % (d.IpInterface, self._currentIpv4Address))

					self._online = True
					eventManager.fire(Events.NETWORK_STATUS, 'online')

			else:
				self._online = False
				self._currentIpv4Address = None
				eventManager.fire(Events.NETWORK_STATUS, 'offline')
				if self._manager.isHotspotActive() is False: #isHotspotActive returns None if not possible
					logger.info('AstroBox is offline. Starting hotspot...')
					result = self._manager.startHotspot() 
					if result is True:
						logger.info('Hostspot started')
					else:
						logger.error('Failed to start hostspot: %s' % result)


class DebianNetworkManager(NetworkManagerBase):
	def __init__(self):
		super(DebianNetworkManager, self).__init__()
		self._nm = NetworkManager
		self._eventListener = NetworkManagerEvents(self)
		self._startHotspotCondition = threading.Condition()

		threads_init()
		self._eventListener.start()
		logger.info('NetworkManagerEvents is listening for signals')

		if not self.settings.getBoolean(['wifi', 'hotspotOnlyOffline']):
			self.startHotspot()

	def close(self):
		self._eventListener.stop()
		self._eventListener = None

	def shutdown(self):
		logging.info('Shutting Down DebianNetworkManager')
		self.close();

	def conectionStatus(self):
		return self._nm.const('state', self._nm.NetworkManager.status())

	def getWifiNetworks(self):
		wifiDevice = self.getWifiDevice()

		networks = {}

		if wifiDevice:
			for ap in wifiDevice.SpecificDevice().GetAccessPoints():
				signal = ap.Strength
				ssid = ap.Ssid

				if ap.Ssid not in networks or signal > networks[ssid]['signal']:
					wpaSecured = True if ap.WpaFlags or ap.RsnFlags else False
					wepSecured = not wpaSecured and ap.Flags == NetworkManager.NM_802_11_AP_FLAGS_PRIVACY

					networks[ssid] = {
						'id': ap.HwAddress,
						'signal': signal,
						'name': ssid,
						'secured': wpaSecured or wepSecured,
						'wep': wepSecured
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

							if type(ap) is NetworkManager.AccessPoint:						
								wpaSecured = True if ap.WpaFlags or ap.RsnFlags else False
								wepSecured = not wpaSecured and ap.Flags == NetworkManager.NM_802_11_AP_FLAGS_PRIVACY

								activeConnections['wireless'] = {
									'id': ap.HwAddress,
									'signal': ap.Strength,
									'name': ap.Ssid,
									'ip': d.Ip4Address,
									'secured': wpaSecured or wepSecured,
									'wep': wepSecured
								}

		return activeConnections

	def getWifiDevice(self):
		devices = self._nm.NetworkManager.GetDevices()
		for d in devices:
			# Return the first MANAGED device that's a WiFi
			if d.Managed and d.DeviceType == self._nm.NM_DEVICE_TYPE_WIFI:
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
				options = {}
				for c in self._nm.Settings.ListConnections():
					currentOptions = c.GetSettings()
					if currentOptions['connection']['id'] == ssid:
						options = currentOptions
						#these are empty and cause trouble when putting it back
						if 'ipv6' in options:
							del options['ipv6']

						if 'ipv4' in options:
							del options['ipv4']
						
						connection = c
						break

				if password:
					if '802-11-wireless-security' in options:
						options['802-11-wireless-security']['psk'] = password

					else:
						options['802-11-wireless-security'] = {
							'psk': password,
						}

				try:
					if connection:
						connection.Update(options)
						self._nm.NetworkManager.ActivateConnection(connection, wifiDevice, accessPoint)
					else:
						options['connection'] = {
							'id': ssid
						}

						(connection, activeConnection) = self._nm.NetworkManager.AddAndActivateConnection(options, wifiDevice, accessPoint)

				except DBusException as e:
					if e.get_dbus_name() == 'org.freedesktop.NetworkManager.InvalidProperty' and e.get_dbus_message() == 'psk':
						return {'message': 'Invalid Password'}
					else:
						raise

				return {
					'name': ssid,
					'id': accessPoint.HwAddress,
					'signal': accessPoint.Strength,
					'ip': wifiDevice.Ip4Address,
					'secured': password is not None,
					'wep': False
				}

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
		with self._startHotspotCondition:
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
