# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from astroprint.network import NetworkManager as NetworkManagerBase

class MacDevNetworkManager(NetworkManagerBase):
	def getWifiNetworks(self):
		return None

	def getActiveNetwork(self):
		return None

	def setWifiNetwork(self, bssid, password):
		return None

	def isHotspotActive(self):
		return False

	def startHotspot(self):
		#return True when succesful
		return "Not supporded on Mac"

	def stopHotspot(self):
		#return True when succesful
		return "Not supporded on Mac"

	def getHostname(self):
		return "astrobox-dev"

	def setHostname(self, name):
		return None
