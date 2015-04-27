# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from astroprint.network import NetworkManager as NetworkManagerBase

class MacDevNetworkManager(NetworkManagerBase):
	def getActiveConnections(self):
		return {
			'wired': {
				'id': 'localhost',
				'signal': None,
				'name': 'Localhost',
				'ip': '127.0.0.1:5000',
				'secured': True
			},
			'wireless': None,
			'manual': None
		}

	def isOnline(self):
		return True

	def startHotspot(self):
		#return True when succesful
		return "Not supporded on Mac"

	def stopHotspot(self):
		#return True when succesful
		return "Not supporded on Mac"

	def getHostname(self):
		return "astrobox-dev"
