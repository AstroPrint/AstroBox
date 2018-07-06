# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import netifaces
import sarge
import os
import threading
import time

import ext.pynetworkmanager.NetworkManager as NetworkManager

from dbus.exceptions import DBusException
from gi.repository import GObject

from astroprint.network import NetworkManager as NetworkManagerBase

logger = logging.getLogger(__name__)

from tempfile import mkstemp
from shutil import move
from os import remove, close

from octoprint.server import eventManager
from octoprint.events import Events

def idle_add_decorator(func):
    def callback(nm, interface, signal, *args):
        #GObject.idle_add(func, *args)
        func(*args)
    return callback

class NetworkManagerEvents(threading.Thread):
	def __init__(self, manager):
		super(NetworkManagerEvents, self).__init__()
		self.daemon = True
		self._stopped = False
		self._manager = manager
		self._online = None
		self._currentIpv4Address = None
		self._activeDevice = None
		self._activatingConnection = None
		self._setOnlineCondition = threading.Condition()
		self._justActivatedConnection = False

		#listeners
		self._propertiesListener = None
		self._stateChangeListener = None
		self._devicePropertiesListener = None
		self._monitorActivatingListener = None

	def getActiveConnectionDevice(self, connection=None):
		if connection:
			settings = connection.GetSettings()
			uuid = settings['connection']['uuid']

		connections = NetworkManager.NetworkManager.ActiveConnections
		for c in connections:

			if connection and not c.Uuid == uuid:
				continue

			try:
			  if hasattr(c, 'State') and c.State == NetworkManager.NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
					d = c.Devices[0]
					return d
			except:
				#ignore errors, some connections are stale and give dbus exceptions
				pass

		return None

	def run(self):
		self._stopped = False
		self._loop = GObject.MainLoop()

		self._propertiesListener = NetworkManager.NetworkManager.OnPropertiesChanged(self.propertiesChanged)
		self._stateChangeListener = NetworkManager.NetworkManager.OnStateChanged(self.globalStateChanged)

		connectionState = NetworkManager.NetworkManager.State
		logger.info('Network Manager reports state: *[%s]*' % NetworkManager.const('state', connectionState))
		if connectionState == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
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

			except KeyboardInterrupt:
				#kill the main process too
				from octoprint import astrobox
				astrobox.stop()

			except DBusException as e:
				#GObject.idle_add(logger.error, 'Exception during NetworkManagerEvents: %s' % e)
				logger.error('Exception during NetworkManagerEvents: %s' % e)

			finally:
				self.stop()


	def stop(self):
		if not self._stopped:
			logger.info('NetworkManagerEvents stopping.')

			if self._propertiesListener:
				NetworkManager.SignalDispatcher.remove_signal_receiver(self._propertiesListener)
				self._propertiesListener = None

			if self._stateChangeListener:
				NetworkManager.SignalDispatcher.remove_signal_receiver(self._stateChangeListener)
				self._stateChangeListener = None

			if self._monitorActivatingListener:
				NetworkManager.SignalDispatcher.remove_signal_receiver(self._monitorActivatingListener)
				self._monitorActivatingListener = None

			if self._devicePropertiesListener:
				NetworkManager.SignalDispatcher.remove_signal_receiver(self._devicePropertiesListener)
				self._devicePropertiesListener = None

			self._stopped = True
			self._loop.quit()

	#@idle_add_decorator
	def globalStateChanged(self, nm, state, interface, signal):
		#uncomment for debugging only
		logger.info('Network Global State Changed, new(%s)' % NetworkManager.const('state', state))
		if state == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
			self._setOnline(True)

		elif self._justActivatedConnection and state == NetworkManager.NM_STATE_CONNECTED_LOCAL:
			#local is a transition state when we have just activated a connection, so do nothing
			self._justActivatedConnection = False

		elif state != NetworkManager.NM_STATE_CONNECTING:
			self._setOnline(False)

	#@idle_add_decorator
	def propertiesChanged(self, nm, properties, interface, signal):
		if "ActiveConnections" in properties:
			#if len(properties['ActiveConnections']) == 0:
			#	self._setOnline(False)
			#	return

			#elif not self._monitorActivatingListener:
			if not self._monitorActivatingListener:
				for c in properties['ActiveConnections']:
					try:
						if hasattr(c, 'State') and c.State == NetworkManager.NM_ACTIVE_CONNECTION_STATE_ACTIVATING:
							if self._monitorActivatingListener:
								NetworkManager.SignalDispatcher.remove_signal_receiver(self._monitorActivatingListener)

							eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {'status': 'connecting'})

							self._activatingConnection = c.Connection
							self._justActivatedConnection = False
							self._monitorActivatingListener = c.Devices[0].OnStateChanged(self.monitorActivatingConnection)

							settings = c.Connection.GetSettings()
							if settings:
								logger.info('Activating Connection %s' % settings['connection']['id'])

							return

					except NetworkManager.ObjectVanished:
						pass

		if "State" in properties and properties["State"] == NetworkManager.NM_STATE_CONNECTED_GLOBAL:
			self._setOnline(True)

	#@idle_add_decorator
	def monitorActivatingConnection(self, nm, new_state, old_state, reason, interface, signal):
		try:
			logger.info('Activating State Change %s -> %s' % (NetworkManager.const('device_state', old_state),NetworkManager.const('device_state', new_state)))
			if self._activatingConnection:
				if new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
					if self._monitorActivatingListener:
						NetworkManager.SignalDispatcher.remove_signal_receiver(self._monitorActivatingListener)
						self._monitorActivatingListener = None

					d = self.getActiveConnectionDevice(self._activatingConnection)
					if d.DeviceType == NetworkManager.NM_DEVICE_TYPE_ETHERNET:
						eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {
							'status': 'connected',
							'info': {
								'type': 'ethernet',
								'ip': self._manager._getIpAddress(d)
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
								'ip': self._manager._getIpAddress(d)
							}
						})

					self._activatingConnection = None
					self._justActivatedConnection = True
					self._setOnline(True)

				elif new_state in [NetworkManager.NM_DEVICE_STATE_FAILED, NetworkManager.NM_DEVICE_STATE_UNKNOWN]:
					logger.warn('Connection reached state %s, reason: %s' % (NetworkManager.const('device_state', new_state), NetworkManager.const('device_state_reason', reason) ) )

					#It has reached and end state.
					self._activatingConnection = None
					if self._monitorActivatingListener:
						NetworkManager.SignalDispatcher.remove_signal_receiver(self._monitorActivatingListener)
						self._monitorActivatingListener = None

					eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {'status': 'failed', 'reason': NetworkManager.const('device_state_reason', reason)})

				elif new_state == NetworkManager.NM_DEVICE_STATE_DISCONNECTED:
					if self._monitorActivatingListener:
						NetworkManager.SignalDispatcher.remove_signal_receiver(self._monitorActivatingListener)
						self._monitorActivatingListener = None

					eventManager.fire(Events.INTERNET_CONNECTING_STATUS, {'status': 'disconnected'})

					self._activatingConnection = None

					#check the global connection status before setting it to false
					#if NetworkManager.NetworkManager.state() != NetworkManager.NM_STATE_CONNECTED_GLOBAL:
					#	self._setOnline(False)
		except Exception, e:
			logger.error(e, exc_info= True)

	#@idle_add_decorator
	def activeDeviceConfigChanged(self, nm, properties, interface, signal):
		if "Options" in properties and "ip_address" in properties["Options"] and properties["Options"]["ip_address"] != self._currentIpv4Address:
			self._currentIpv4Address = properties["Options"]["ip_address"]
			#self._setOnline(True)
			eventManager.fire(Events.NETWORK_IP_CHANGED, self._currentIpv4Address)

	def _setOnline(self, value):
		with self._setOnlineCondition:
			if value == self._online:
				return

			if value:
				try:
					d = self.getActiveConnectionDevice()

					if d:
						self._activeDevice = d
						if self._devicePropertiesListener:
							NetworkManager.SignalDispatcher.remove_signal_receiver(self._devicePropertiesListener)
							self._devicePropertiesListener = None # in case something fails on reconnection so it's not wrongly thinking we're still listening

						self._currentIpv4Address = self._manager._getIpAddress(d)

						try:
							self._devicePropertiesListener = d.Dhcp4Config.OnPropertiesChanged(self.activeDeviceConfigChanged)
						except AttributeError:
							logger.warn('DHCP4 Config not avaialable')

						logger.info('Active Connection is now %s (%s)' % (d.IpInterface, self._currentIpv4Address))

						self._online = True
						eventManager.fire(Events.NETWORK_STATUS, 'online')

				except Exception as e:
					logger.error(e, exc_info=1)

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
		self._activeWifiDevice = None
		self._eventListener = NetworkManagerEvents(self)
		self._startHotspotCondition = threading.Condition()
		self._hostname = None

	def startUp(self):
		logger.info("Starting communication with Network Manager - version [%s]" % self._nm.NetworkManager.Version )
		self._eventListener.start()
		logger.info('NetworkManagerEvents is listening for signals')

		if not self.settings.getBoolean(['wifi', 'hotspotOnlyOffline']):
			self.startHotspot()

		#Find out and set the active WiFi Device
		self._activeWifiDevice = self._getWifiDevice()

	def close(self):
		self._eventListener.stop()
		self._eventListener = None

	def shutdown(self):
		logger.info('Shutting Down DebianNetworkManager')
		self.close()

	def conectionStatus(self):
		return self._nm.const('state', self._nm.NetworkManager.status())

	def getWifiNetworks(self):
		wifiDevice = self._activeWifiDevice

		networks = {}

		if wifiDevice:
			for ap in wifiDevice.SpecificDevice().GetAccessPoints():
				try:
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
				except NetworkManager.ObjectVanished:
					pass

			return [v for k,v in networks.iteritems()]

		return None

	def getActiveConnections(self):
		activeConnections = { 'wired': None, 'wireless': None, 'manual': None}

		if self._nm.NetworkManager.State == self._nm.NM_STATE_CONNECTED_GLOBAL:
			connections = self._nm.NetworkManager.ActiveConnections
			for c in connections:
				if hasattr(c, 'State') and c.State == self._nm.NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
					d = c.Devices[0]

					if d.DeviceType == self._nm.NM_DEVICE_TYPE_ETHERNET:
						if not activeConnections['wired']:
							activeConnections['wired'] = {
								'id': d.SpecificDevice().HwAddress,
								'ip': self._getIpAddress(d)
							}

					elif d.DeviceType == self._nm.NM_DEVICE_TYPE_WIFI:
						if not activeConnections['wireless']:

							ap = d.SpecificDevice().ActiveAccessPoint

							if type(ap) is NetworkManager.AccessPoint:
								wpaSecured = True if ap.WpaFlags or ap.RsnFlags else False
								wepSecured = not wpaSecured and ap.Flags == NetworkManager.NM_802_11_AP_FLAGS_PRIVACY

								activeConnections['wireless'] = {
									'id': ap.HwAddress,
									'signal': ap.Strength,
									'name': ap.Ssid,
									'ip': self._getIpAddress(d),
									'secured': wpaSecured or wepSecured,
									'wep': wepSecured
								}

		return activeConnections

	def isHotspotable(self):
		return bool(self.settings.get(['wifi', 'hotspotDevice'])) and self.isHotspotActive() != None

	def hasWifi(self):
		return bool(self._activeWifiDevice)

	def isOnline(self):
		return self._eventListener._online

	def setWifiNetwork(self, bssid, password = None):
		wifiDevice = self._activeWifiDevice

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
						activeConnection = self._nm.NetworkManager.ActivateConnection(connection, wifiDevice, accessPoint)

						try:
							if connection == activeConnection.Connection and activeConnection.State > 0:
								return {
									'name': ssid,
									'id': accessPoint.HwAddress,
									'signal': accessPoint.Strength,
									'ip': None,
									'secured': password is not None,
									'wep': False
								}

						except NetworkManager.ObjectVanished:
							pass

						### The Connection couldn't be activated. Delete it
						return None

					else:
						options['connection'] = {
							'id': ssid
						}

						(connection, activeConnection) = self._nm.NetworkManager.AddAndActivateConnection(options, wifiDevice, accessPoint)

						try:
							if connection == activeConnection.Connection and activeConnection.State > 0:
								return {
									'name': ssid,
									'id': accessPoint.HwAddress,
									'signal': accessPoint.Strength,
									'ip': None,
									'secured': password is not None,
									'wep': False
								}

						except NetworkManager.ObjectVanished:
							pass

						### The Connection couldn't be activated. Delete it
						connection.Delete()
						return None


				except DBusException as e:
					if e.get_dbus_name() == 'org.freedesktop.NetworkManager.InvalidProperty' and e.get_dbus_message() == 'psk':
						return {
							'err_code': 'invalid_psk',
							'message': 'Invalid Password'
						}

					else:
						raise

		return None

	def storedWifiNetworks(self):
		result = []

		activeConnections = [c.Uuid for c in NetworkManager.NetworkManager.ActiveConnections]

		for c in self._nm.Settings.ListConnections():
			s = c.GetSettings()
			if '802-11-wireless' in s and 'connection' in s:
				result.append({
					'id': s['connection']['uuid'],
					'name': s['802-11-wireless']['ssid'],
					'active': s['connection']['uuid'] in activeConnections
				})

		return result

	def deleteStoredWifiNetwork(self, networkId):
		for c in self._nm.Settings.ListConnections():
			s = c.GetSettings()
			if 'connection' in s and s['connection']['uuid'] == networkId:
				c.Delete()
				return True

		return False

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
			isHotspotActive = self.isHotspotActive()

			if isHotspotActive is None: # this means is not possible in this system
				return "Hotspot is not possible on this system"

			if isHotspotActive is True:
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
		if not self._hostname:
			self._hostname = self._nm.Settings.Hostname

		return self._hostname

	def setHostname(self, name):
		old_name = self.getHostname()

		if old_name == name:
			return True

		settings = self._nm.Settings
		newName = ''

		try:
			settings.SaveHostname(name)
			newName = settings.Hostname

		except DBusException as e:
			exceptionName = e.get_dbus_name()

			if exceptionName == 'org.freedesktop.DBus.Error.NoReply':
				newName = name

		if (newName == name):
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

			self._hostname = name

			return True
		else:
			return False

	@property
	def activeIpAddress(self):
		return self._eventListener._currentIpv4Address

# ~~~~~~~~~~~~ Private Functions ~~~~~~~~~~~~~~~

	def _getWifiDevice(self):
		devices = self._nm.NetworkManager.GetDevices()
		wifiDevices = []

		for d in devices:
			# Return the first MANAGED device that's a WiFi
			if d.Managed and d.DeviceType == self._nm.NM_DEVICE_TYPE_WIFI:
				wifiDevices.append(d)

		if wifiDevices:
			if len(wifiDevices) == 1:
				d = wifiDevices[0]
				logger.info('Found one WiFi interface [%s], using it.' % d.Interface)
				return d

			else:
				logger.info('Found multiple WiFi devices [%s], looking for the configured one to use...' % ', '.join([d.Interface for d in wifiDevices]))
				configuredWifiIf = self.settings.get(['network', 'interface'])

				for d in wifiDevices:
					if d.Interface == configuredWifiIf:
						logger.info('Using Configured WiFi Interface: [%s]' % d.Interface)
						return d

				#The on in settings is not found, use the first avaiable one
				d = wifiDevices[0]
				logger.warn('Configured WiFi Interface [%s] not found. Using: [%s]' % (configuredWifiIf, d.Interface))
				return d

		return False

	def _getIpAddress(self, device):
		try:
			if device.Ip4Config:
				if not hasattr(device.Ip4Config, 'AddressData'):
					if hasattr(device.Ip4Config, 'Addresses'):
						return device.Ip4Config.Addresses[0][0]
					elif device.Ip4Address and device.Ip4Address != '0.0.0.0':
						return device.Ip4Address
				else:
					return device.Ip4Config.AddressData[0]['address']

		except AttributeError:
			pass

		return None

