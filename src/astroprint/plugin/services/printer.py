# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events
from astroprint.camera import cameraManager
from astroprint.network.manager import networkManager
from astroprint.boxrouter import boxrouterManager
from astroprint.printer.manager import printerManager

class PrinterService(PluginService):
	_validEvents = [
		#watch the printer's connection state with Astrobox (via USB): connected or disconnected
		'printer_state_changed'
	]

	def __init__(self):
		super(PrinterService, self).__init__()
		self._eventManager.subscribe(Events.CONNECTED, self._onConnect)
		self._eventManager.subscribe(Events.DISCONNECTED, self._onDisconnect)

	#REQUESTS

	def getStatus(self):
		printer = printerManager()
		cm = cameraManager()

		fileName = None

		if printer.isPrinting():
			currentJob = printer.getCurrentJob()
			fileName = currentJob["file"]["name"]

		return {
				'id': boxrouterManager().boxId,
				'name': networkManager().getHostname(),
				'printing': printer.isPrinting(),
				'fileName': fileName,
				'printerModel': None,
				'material': None,
				'operational': printer.isOperational(),
				'paused': printer.isPaused(),
				'camera': cm.isCameraConnected(),
				#'printCapture': cm.timelapseInfo,
				'remotePrint': True,
				'capabilities': ['remotePrint'] + cm.capabilities
			}


	def getConnection(self):

		pm = printerManager()

		state, port, baudrate = pm.getCurrentConnection()
		current = {
			"state": state,
			"port": port,
			"baudrate": baudrate
		}

		return { 'current': current, 'option': pm.getConnectionOptions() }

	def setPrinterCommand(self,data):
		print 'data'

	def getTemperature(self):
		pm = printerManager()

		tempData = pm.getCurrentTemperatures()

		print 'getTemperature'
		print tempData

		return {}


	#EVENTS

	def _onConnect(self,event,value):
		self.publishEvent('printer_state_changed','connected')

	def _onDisconnect(self,event,value):
		self.publishEvent('printer_state_changed','disconnected')
