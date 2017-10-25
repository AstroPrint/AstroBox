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

	def printerPrintheadCommand(self, data, callback):
		self._logger.info('printerPrintheadCommand')
		self._logger.info(data)
		self._logger.info(callback)
		self._logger.info('-----------------------')
		pm = printerManager()

		command = 'jog'
		axis = data

		if not pm.isOperational() or pm.isPrinting():
			# do not jog when a print job is running or we don't have a connection
			callback("Printer is not operational or currently printing",True)

		valid_commands = {
			"jog": [],
			"home": ["axes"]
		}

		valid_axes = ["x", "y", "z"]
		##~~ jog command
		if command == "jog":
			# validate all jog instructions, make sure that the values are numbers

			self._logger.info('jog')
			validated_values = {}
			for axis in valid_axes:
				self._logger.info('axis')
				self._logger.info(axis)
				try:
					value = data[axis]
				except:
					value = None
				self._logger.info('value')
				self._logger.info(value)
				if not isinstance(value,(int,long,float)):
					self._logger.info('not a number')
				else:
					validated_values[axis] = value
					self._logger.info('value added')

			self._logger.info('before ex')
			self._logger.info(validated_values['x'])

			# execute the jog commands
			for axis, value in validated_values.iteritems():
				self._logger.info('pm')
				self._logger.info('axis %s',axis)
				self._logger.info('value &s',value)
				pm.jog(axis, value)

		##~~ home command
		elif command == "home":
			validated_values = []
			axes = axis
			for axis in axes:
				if not axis in valid_axes:
					callback("Invalid axis: " + axis,True)
				validated_values.append(axis)

			# execute the home command
			pm.home(validated_values)

		callback({'success': 'no_error'})


	#EVENTS

	def _onConnect(self,event,value):
		self.publishEvent('printer_state_changed','connected')

	def _onDisconnect(self,event,value):
		self.publishEvent('printer_state_changed','disconnected')
