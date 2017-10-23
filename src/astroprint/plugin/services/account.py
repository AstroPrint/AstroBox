# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events

class AccountService(PluginService):
	_validEvents = ['account_state_change']

	def __init__(self):
		super(AccountService, self).__init__()
		self._eventManager.subscribe(Events.ASTROPRINT_STATUS, self.onAccountStateChange)

	def onAccountStateChange(self,event,value):
			print 'onAccountStateChange'
			self.publishEvent('account_state_change',value)
