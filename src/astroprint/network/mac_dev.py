# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import threading

from octoprint.server import eventManager
from octoprint.events import Events

from astroprint.network import NetworkManager as NetworkManagerBase

class MacDevNetworkManager(NetworkManagerBase):
	def __init__(self):
		self.name = "astrobox-dev"
		self.logger = logging.getLogger(__name__)
		self._online = False

		super(MacDevNetworkManager, self).__init__()

	def startUp(self):
		offlineTime = 3.0
		timer = threading.Timer(offlineTime, self._goOnline)
		timer.daemon = True
		timer.start()

		self.logger.info('Mac Dev Network Manager initialized. Simulating %d secs to go online' % offlineTime)

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

	def storedWifiNetworks(self):
		return [
			{'id': '1', 'name': 'Test Connection 1', 'active': True},
			{'id': '2', 'name': 'Test Connection 2', 'active': False},
			{'id': '3', 'name': 'Test Connection 3', 'active': False}
		]

	def deleteStoredWifiNetwork(self, networkId):
		return ( networkId in [c['id'] for c in self.storedWifiNetworks()] )

	def hasWifi(self):
		return True

	def getWifiNetworks(self):
		return [
				{"id": "80:1F:02:F9:16:1B", "name": "Test Connection 1", "secured": True, "signal": 54, "wep": False},
				{"id": "80:1F:02:F9:16:1B", "name": "creatorpro", "secured": False, "signal": 54, "wep": False},
				{"id": "76:DA:38:68:50:E9", "name": "wanhao", "secured": False, "signal": 80, "wep": False},
				{"id": "74:DA:38:88:51:90", "name": "soniabox", "secured": False, "signal": 59, "wep": False},
				{"id": "C0:7B:BC:1A:5C:81", "name": "Empresas", "secured": True, "signal": 37, "wep": False},
				{"id": "C0:7B:BC:1A:5C:80", "name": "CITIC", "secured": True, "signal": 37, "wep": False},
				{"id": "2C:4D:54:CC:30:F8", "name": "AstroPrintWLAN", "secured": True, "signal": 100, "wep": False},
				{"id": "C0:7B:BC:1A:5C:82", "name": "InvitadosEmpresas", "secured": False, "signal": 39, "wep": False}]


	def isOnline(self):
		return self._online

	def startHotspot(self):
		#return True when succesful
		return "Not supporded on Mac"

	def stopHotspot(self):
		#return True when succesful
		return "Not supporded on Mac"

	def getHostname(self):
		return self.name

	def setHostname(self, name):
		self.name = name
		self.logger.info('Host name is set to %s ' % name)
		return True

	@property
	def activeIpAddress(self):
		return '127.0.0.1'

	def _goOnline(self):
		eventManager.fire(Events.NETWORK_STATUS, 'online')
		self._online = True
