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

	##Printer status

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

	##Printhead movement

	def printerPrintheadCommand(self, data, callback):
		pm = printerManager()

		if not pm.isOperational() or pm.isPrinting():
			# do not jog when a print job is running or we don't have a connection
			callback("Printer is not operational or currently printing",True)

		valid_axes = ["x", "y", "z"]

		validated_values = {}
		for axis in valid_axes:
			try:
				value = data[axis]
			except:
				value = None
			if isinstance(value,(int,long,float)):
				validated_values[axis] = value

		if len(validated_values) <= 0:
			self._logger.error('not a number')
			callback('movement value is not a number',True)
		else:
			# execute the jog commands
			for axis, value in validated_values.iteritems():
				pm.jog(axis, value)

		callback({'success': 'no_error'})


	def printerHomeCommand(self,axes,callback):
		pm = printerManager()

		self._logger.info('printerHomeCommand')

		self._logger.info(axes)

		valid_axes = ["xy", "z"]

		if not axes in valid_axes:
			callback("Invalid axes: " + axes,True)

		if axes == 'xy':
			self._logger.info('xy home')
			pm.home('x')
			pm.home('y')
		else:
			self._logger.info('z home')
			pm.home('z')

		callback({'success': 'no_error'})

	##Printer connection

	def getConnection(self):

		pm = printerManager()

		state, port, baudrate = pm.getCurrentConnection()
		current = {
			"state": state,
			"port": port,
			"baudrate": baudrate
		}

		return { 'current': current, 'option': pm.getConnectionOptions() }


	def connectionCommand(self,data,callback):
		valid_commands = {
			"connect": ["autoconnect"],
			"disconnect": []
		}

		pm = printerManager()

		command = data['command']

		if command == "connect":
			s = settings()

			port = None
			baudrate = None

			options = pm.getConnectionOptions()

			if "port" in data:
				port = data["port"]
				if port not in options["ports"]:
					callback('Invalid port: ' + port,True)

					return

			if "baudrate" in data:
				baudrate = int(data["baudrate"])
				if baudrate:
					baudrates = options["baudrates"]
					if baudrates and baudrate not in baudrates:
						callback('Invalid baudrate: ' + baudrate,True)

						return

				else:
					callback('Baudrate is null',True)

					return

			if "save" in data and data["save"]:
				s.set(["serial", "port"], port)
				s.setInt(["serial", "baudrate"], baudrate)

			if "autoconnect" in data:
				s.setBoolean(["serial", "autoconnect"], data["autoconnect"])

			s.save()

			pm.connect(port=port, baudrate=baudrate)

		elif command == "disconnect":
			pm.disconnect()

		callback({'success': 'no_error'})


	##Temperature

	def getTemperature(self):
		pm = printerManager()

		tempData = pm.getCurrentTemperatures()

		self._logger.info('getTemperature')
		self._logger.info(tempData)

		return tempData

	#EVENTS

	def _onConnect(self,event,value):
		self.publishEvent('printer_state_changed','connected')

	def _onDisconnect(self,event,value):
		self.publishEvent('printer_state_changed','disconnected')
