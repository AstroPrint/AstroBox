# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import netifaces
import sarge

#This needs to happen before importing NetworkManager
from dbus.mainloop.glib import DBusGMainLoop; DBusGMainLoop(set_as_default=True)
import NetworkManager

from dbus.exceptions import DBusException

from octoprint.network import NetworkManager as NetworkManagerBase

logger = logging.getLogger(__name__)

class UbuntuNetworkManager(NetworkManagerBase):
	def getWifiNetworks(self):
		interface = self.settings.get(['wifi', 'internetInterface'])
		wifiDevice = NetworkManager.NetworkManager.GetDeviceByIpIface(interface).SpecificDevice()

		networks = [{
			'id': ap.HwAddress,
			'signal': ord(ap.Strength),
			'name': ap.Ssid,
			'secured': True if ap.WpaFlags or ap.RsnFlags else False} for ap in wifiDevice.GetAccessPoints()]

		return networks

	def getActiveWifiNetwork(self):
		interface = self.settings.get(['wifi', 'internetInterface'])
		wifiDevice = NetworkManager.NetworkManager.GetDeviceByIpIface(interface)
		connection = wifiDevice.ActiveConnection

		if connection != '/':
			ap = connection.SpecificObject
			network = {
				'id': ap.HwAddress,
				'signal': ord(ap.Strength),
				'name': ap.Ssid,
				'secured': True if ap.WpaFlags or ap.RsnFlags else False}

			return network

		else:
			return False

	def setWifiNetwork(self, bssid, password = None):
		if bssid:
			interface = self.settings.get(['wifi','internetInterface'])
			wifiDevice = NetworkManager.NetworkManager.GetDeviceByIpIface(interface)

			accessPoint = None

			for ap in wifiDevice.SpecificDevice().GetAccessPoints():
				if ap.HwAddress == bssid:
					accessPoint = ap
					break

			if accessPoint:
				ssid = accessPoint.Ssid
				connection = None
				for c in NetworkManager.Settings.ListConnections():
					if c.GetSettings()['connection']['id'] == ssid:
						connection = c
						break

				try:
					if connection:
						NetworkManager.NetworkManager.ActivateConnection(connection, wifiDevice, "/")
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

						(connection, activeConnection) = NetworkManager.NetworkManager.AddAndActivateConnection(options, wifiDevice, accessPoint)

				except DBusException as e:
					if e.get_dbus_name() == 'org.freedesktop.NetworkManager.InvalidProperty' and e.get_dbus_message() == 'psk':
						return {'message': 'Invalid Password'}
					else:
						raise

				import gobject
				loop = gobject.MainLoop()

				result = {}

				def connectionStateChange(new_state, old_state, reason):
					r = result
					if new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
						result['ssid'] = ssid
						loop.quit()
					elif new_state == NetworkManager.NM_DEVICE_STATE_FAILED:
						connection.Delete()
						result['message'] = "The connection could not be created"
						loop.quit()

				wifiDevice.connect_to_signal('StateChanged', connectionStateChange)

				loop.run()

				return result

		return None

	def isHotspotActive(self):
		interface = self.settings.get(['wifi', 'hotspotInterface'])

		info = netifaces.ifaddresses(interface)

		return netifaces.AF_INET in info

	def startHotspot(self):
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