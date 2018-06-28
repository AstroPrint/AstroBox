# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService

from netifaces import interfaces, ifaddresses, AF_INET

from octoprint.events import Events
from astroprint.network.manager import networkManager

class NetworkService(PluginService):
	_validEvents = [
		#watch the state of the connection with astroprint.com: online or offline
		'network_status_change',
		#watch the state the network connection while it's connecting: connecting, connected, failed, disconnected
		'internet_connecting_status_change'
	]

	def __init__(self):
		super(NetworkService, self).__init__()
		self._eventManager.subscribe(Events.NETWORK_STATUS, self.onNetworkStatusChange)
		self._eventManager.subscribe(Events.INTERNET_CONNECTING_STATUS, self.onInternetConnectingStatus)

	#EVENTS

	def onNetworkStatusChange(self,event,value):
		self.publishEvent('network_status_change', value)

	def onInternetConnectingStatus(self, event, value):
		self.publishEvent('internet_connecting_status_change', value)

	#REQUESTS

	def getNetworkStatus(self):
		nm = networkManager()
		return ('online' if nm.isOnline() else 'offline')

	def getMyIP(self, data, sendResponse):
		addresses = {}

		for ifaceName in interfaces():
			addrs = [i['addr'] for i in ifaddresses(ifaceName).setdefault(AF_INET, [{'addr':None}] )]
			addresses[ifaceName] = addrs

		if 'eth0' in addresses and addresses['eth0'][0] is not None:
			sendResponse(addresses['eth0'])
			return

		if 'wlan0' in addresses and addresses['wlan0'][0] is not None:
			sendResponse(addresses['wlan0'])
			return

		if 'en0' in addresses and addresses['en0'][0] is not None:
			sendResponse(addresses['en0'])
			return

		sendResponse(None)

	def checkInternet(self, data, sendResponse):
		nm = networkManager()

		if nm.isAstroprintReachable():
		#if False:
			return sendResponse({'connected':True})
		else:
			networks = nm.getWifiNetworks()

			if networks:
				return sendResponse(
					{
						'networks':networks,
						'connected':False
					}
				)
			else:
				return sendResponse("unable_get_wifi",True)

	def networkName(self, newName, sendMessage):
		nm = networkManager()

		if newName :
				nm.setHostname(newName)

		sendMessage({'name':nm.getHostname()})

	def networkSettings(self, data, sendMessage):
		nm = networkManager()

		sendMessage({
			'networks': nm.getActiveConnections(),
			'hasWifi': nm.hasWifi(),
			'storedWifiNetworks': nm.storedWifiNetworks()
		})

	def wifiNetworks(self, data, sendMessage):
		networks = networkManager().getWifiNetworks()

		if networks:
			sendMessage(networks)
		else:
			sendMessage("unable_get_wifi_networks",True)

	def setWifiNetwork(self, data, sendMessage):
		if 'id' in data and 'password' in data:
			result = networkManager().setWifiNetwork(data['id'], data['password'])

			if result:
				if 'err_code' in result:
					sendMessage(result['err_code'], True)
				else:
					sendMessage(result)
			else:
				sendMessage('network_not_found',True)

			return

		sendMessage('incorrect_data',True)

	def deleteStoredWiFiNetwork(self, data, sendMessage):
		nm = networkManager()

		if nm.deleteStoredWifiNetwork(data['id']):
			sendMessage({'success': 'no_error'})
		else:
			sendMessage("network_not_found",True)
