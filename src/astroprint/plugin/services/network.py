# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events

class NetworkService(PluginService):
	_validEvents = ['network_status_change']

	def __init__(self):
		super(NetworkService, self).__init__()
		self._eventManager.subscribe(Events.NETWORK_STATUS, self.onNetworkStatusChange)

	def onNetworkStatusChange(self,event,value):
		print 'onNetworkStatusChange'

		self.publishEvent('network_status_change',event,{
			'isOnline': (value == 'online')
		})
