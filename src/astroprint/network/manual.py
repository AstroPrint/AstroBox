# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from octoprint.settings import settings

from astroprint.network import NetworkManager as NetworkManagerBase

class ManualNetworkManager(NetworkManagerBase):
	def getActiveConnections(self):
		interface = settings().get(['network', 'interface'])

		if 'wlan' in interface:
			return {
				'wired': None,
				'wireless': {
					'id': 'manual',
					'signal': None,
					'name': 'Manually Configured',
					'ip': '0.0.0.0',
					'secured': False
				}
			}

		else: 
			return {
				'wired': {
					'id': 'manual',
					'signal': None,
					'name': 'Manually Configured',
					'ip': '0.0.0.0',
					'secured': True
				},
				'wireless': None
			}

	def isOnline(self):
		return True

	def startHotspot(self):
		return False

	def stopHotspot(self):
		return False

	def getHostname(self):
		return "astrobox-dev"
