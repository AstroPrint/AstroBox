# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import socket
import logging

from octoprint.settings import settings

from astroprint.network import NetworkManager as NetworkManagerBase

class ManualNetworkManager(NetworkManagerBase):
	def __init__(self):
		super(ManualNetworkManager, self).__init__()
		self._logger = logging.getLogger(__name__)
		self._ipAddress = None

	def startUp(self):
		#obtain IP address
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('8.8.8.8', 0))
		self._ipAddress = s.getsockname()[0]
		self._logger.info('Manual Network Manager initialized with IP %s' % self._ipAddress)

	def getActiveConnections(self):
		return {
			'wired': None,
			'wireless': None,
			'manual': {
				'ip': self._ipAddress,
				'interface': 'Not Available'
			}
		}

	@property
	def activeIpAddress(self):
		return self._ipAddress

	def isOnline(self):
		return True

	def startHotspot(self):
		return False

	def stopHotspot(self):
		return False

	def getHostname(self):
		return socket.gethostname()

