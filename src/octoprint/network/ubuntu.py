# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

#This needs to happen before importing NetworkManager
from dbus.mainloop.glib import DBusGMainLoop; DBusGMainLoop(set_as_default=True)
import NetworkManager

from dbus.exceptions import DBusException

from octoprint.network import NetworkManager as NetworkManagerBase

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
			return None

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
						(connection, activeConnection) = NetworkManager.NetworkManager.AddAndActivateConnection({
							'connection': {
								'id': ssid
							},
							'802-11-wireless-security': {
								'psk': password
							}
						}, wifiDevice, accessPoint)

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