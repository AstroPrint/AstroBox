# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import socket

from octoprint.settings import settings

from astroprint.network import NetworkManager as NetworkManagerBase

class ManualNetworkManager(NetworkManagerBase):
	def getActiveConnections(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('8.8.8.8', 0))
		ipAddress = s.getsockname()[0]

		return {
			'wired': None,
			'wireless': None,
			'manual': {
				'ip': ipAddress,
				'interface': settings().get(['network', 'interface'])
			}
		}

	def isOnline(self):
		return True

	def startHotspot(self):
		return False

	def stopHotspot(self):
		return False

	def getHostname(self):
		return socket.gethostname()

