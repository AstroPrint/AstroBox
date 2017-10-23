# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events

class PrinterService(PluginService):
	_validEvents = ['printer_state_changed']

	def __init__(self):
		super(PrinterService, self).__init__()
		self._eventManager.subscribe(Events.CONNECTED, self.connect)
		self._eventManager.subscribe(Events.DISCONNECTED, self.disconnect)

	def connect(self,event,value):
		self.publishEvent('printer_state_changed',{'Connected'})

	def disconnect(self,event,value):
		self.publishEvent('printer_state_changed',{'Disconnected'})
