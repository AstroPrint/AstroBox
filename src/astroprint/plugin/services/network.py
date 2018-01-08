# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events
from astroprint.network import NetworkManager

class NetworkService(PluginService):
	_validEvents = [
		#watch the state of the connection with astroprint.com: online or offline
		'network_status_change'
	]

	def __init__(self):
		super(NetworkService, self).__init__()
		self._eventManager.subscribe(Events.NETWORK_STATUS, self.onNetworkStatusChange)

	#REQUESTS

	def getNetworkStatus(self):
		nm = NetworkManager()
		return ('online' if nm.checkOnline() else 'offline')


	#EVENTS

	def onNetworkStatusChange(self,event,value):
		self.publishEvent('network_status_change',('online' if value == 'online' else 'offline'))
