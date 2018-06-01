# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.events import Events
from octoprint.settings import settings
from astroprint.camera import cameraManager
from astroprint.network.manager import networkManager
from astroprint.boxrouter import boxrouterManager
from astroprint.printer.manager import printerManager
from astroprint.printerprofile import printerProfileManager

class PrinterService(PluginService):
	_validEvents = [
		#watch the printer's status. Returns and Object with a state and a value
		'printer_state_changed',
		#watch the timelapse selected for photos capture while printing. Return the frequence value.
		'print_capture_info_changed',
		#watch the temperature changes. Return object containing [tool0: actual, target - bed: actual, target]
		'temperature_changed',
		#watch the printing progress. Returns Object containing [completion, currentLayer, filamentConsumed, filepos, printTime, printTimeLeft]
		'printing_progress_changed',
		#watch the current printing state
		'printing_state_changed'
	]

	def __init__(self):
		super(PrinterService, self).__init__()
		#printer status
		self._eventManager.subscribe(Events.CONNECTED, self._onConnect)
		self._eventManager.subscribe(Events.DISCONNECTED, self._onDisconnect)
		self._eventManager.subscribe(Events.CONNECTING, self._onConnecting)
		self._eventManager.subscribe(Events.HEATING_UP, self._onHeatingUp)
		self._eventManager.subscribe(Events.TOOL_CHANGE, self._onToolChange)
		self._eventManager.subscribe(Events.PRINTINGSPEED_CHANGE, self._onPrintingSpeedChange)
		self._eventManager.subscribe(Events.PRINTINGFLOW_CHANGE, self._onPrintingFlowChange)

		#temperature
		self._eventManager.subscribe(Events.TEMPERATURE_CHANGE, self._onTemperatureChanged)

		#printing progress
		self._eventManager.subscribe(Events.PRINTING_PROGRESS, self._onPrintingProgressChanged)

		#printing timelapse
		self._eventManager.subscribe(Events.CAPTURE_INFO_CHANGED, self._onPrintCaptureInfoChanged)

		#printing handling
		self._eventManager.subscribe(Events.PRINT_STARTED, self._onPrintStarted)
		self._eventManager.subscribe(Events.PRINT_DONE, self._onPrintDone)
		self._eventManager.subscribe(Events.PRINT_FAILED, self._onPrintFailed)
		self._eventManager.subscribe(Events.PRINT_CANCELLED, self._onPrintCancelled)
		self._eventManager.subscribe(Events.PRINT_PAUSED, self._onPrintPaused)
		self._eventManager.subscribe(Events.PRINT_RESUMED, self._onPrintResumed)
		self._eventManager.subscribe(Events.ERROR, self._onPrintingError)


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

		valid_axes = ["xy", "z"]

		if not axes in valid_axes:
			callback("Invalid axes: " + axes,True)

		if axes == 'xy':
			pm.home('x')
			pm.home('y')
		else:
			pm.home('z')

		callback({'success': 'no_error'})

	def printerPrintingSpeed(self, data, callback):
		pm = printerManager()

		amount = data["amount"]

		pm.printingSpeed(amount)

		callback({'success': 'no_error'})

	def printerFanSpeed(self, data, callback):
		pm = printerManager()

		speed = data["speed"]
		tool = data["tool"]

		pm.fan(tool, speed)

		callback({'success': 'no_error'})

	def sendComm(self, data ,callback):
		pm = printerManager()

		if not pm.allowTerminal:
			callback('Driver does not support terminal access',True)
		if not pm.isOperational():
			callback('No Printer connected',True)

		command = data['command']

		if command:
			pm.sendRawCommand(command)
			callback({'success': 'no_error'})
		else:
			callback("Command is missing", True)

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


	##Temperature

	def getTemperature(self):
		pm = printerManager()

		tempData = pm.getCurrentTemperatures()

		return tempData

	def setTemperature(self,data,callback):

		pm = printerManager()

		if not pm.isOperational():
			callback("Printer is not operational", True)

			return

		temperature = data['temperature']
		element = data['element']

		if not isinstance(temperature, (int, long, float)):
			callback("Not a number: " + temperature, True)
			return
		# perform the actual temperature command
		pm.setTemperature(element, temperature)

		callback({'success': 'no_error'})

	def extrude(self,data,callback):

		pm = printerManager()

		if not pm.isOperational():
			callback("Printer is not operational", True)
			return

		if pm.isPrinting():
			# do not extrude when a print job is running
			callback("Printer is currently printing", True)
			return

		amount = data["amount"]
		speed = data["speed"]
		tool = data["tool"]

		if not isinstance(amount, (int, long, float)):
			callback("Not a number for extrusion amount: " + amount, True)
			return

		if speed and not isinstance(speed, (int, long, float)):
			speed = None

		pm.extrude(tool, amount, speed)

		callback({'success': 'no_error'})
		return

	def getNumberOfExtruders(self,data,sendResponse=None):
		ppm = printerProfileManager()

		extruderCount = ppm.data.get('extruder_count')

		if sendResponse:
			sendResponse(extruderCount)

		return extruderCount

	def getSelectedExtruder(self, data, sendResponse= None):
		pm = printerManager()

		if pm.isConnected():
			selectedTool = pm.getSelectedTool()
		else:
			selectedTool = None

		if sendResponse:
			sendResponse(selectedTool)

		return selectedTool

	def getPrintingSpeed(self, data, sendResponse= None):
		pm = printerManager()

		if pm.isConnected():
			printingSpeed = int(pm.getPrintingSpeed())
		else:
			printingSpeed = None

		if sendResponse:
			sendResponse(printingSpeed)

		return printingSpeed

	def setPrintingSpeed(self, data, sendResponse= None):
		pm = printerManager()

		pm.setPrintingSpeed(int(data))

		sendResponse({'success': 'no_error'})

		return

	def getPrintingFlow(self, data, sendResponse= None):
		pm = printerManager()

		if pm.isConnected():
			printingFlow = int(pm.getPrintingFlow())
		else:
			printingFlow = None

		if sendResponse:
			sendResponse(printingFlow)

		return printingFlow

	def setPrintingFlow(self, data, sendResponse= None):
		pm = printerManager()

		pm.setPrintingFlow(int(data))

		sendResponse({'success': 'no_error'})

		return

	def selectTool(self,data,sendResponse):

		pm = printerManager()

		pm.changeTool(int(data))

		sendResponse({'success': 'no_error'})

		return

	def getPrintJobId(self, data, sendResponse):
		pm = printerManager()

		sendResponse(pm.currentPrintJobId)

	def pause(self,data,sendResponse):
		printerManager().togglePausePrint()
		sendResponse({'success': 'no_error'})

	def resume(self,data,sendResponse):
		printerManager().togglePausePrint()
		sendResponse({'success': 'no_error'})

	def cancel(self,data,sendResponse):
		sendResponse(printerManager().cancelPrint())

	def setTimelapse(self,data,sendResponse):
		freq = data['freq']
		if freq:
			cm = cameraManager()

			if cm.timelapseInfo:
				if not cm.update_timelapse(freq):
					sendResponse('error_updating_timelapse',True)
					return

			else:
				r = cm.start_timelapse(freq)
				if r != 'success':
					sendResponse('error_starting_timelapse',True)
					return
		else:
			sendResponse('erro_no_frequency',True)
			return

		sendResponse({'success': 'no_error'})


	def getTimelapse(self,data,sendResponse):
		sendResponse(cameraManager().timelapseInfo)

	#EVENTS

	def _onConnect(self,event,value):
		self.publishEvent('printer_state_changed', {"operational": True})

	def _onConnecting(self,event,value):
		self.publishEvent('printer_state_changed', {"connecting": True})

	def _onDisconnect(self,event,value):
		self.publishEvent('printer_state_changed', {"operational": False})

	def _onToolChange(self,event,value):
		self.publishEvent('printer_state_changed', {"tool": value})

	def _onPrintingSpeedChange(self,event,value):
		self.publishEvent('printer_state_changed', {"speed": value})

	def _onPrintingFlowChange(self,event,value):
		self.publishEvent('printer_state_changed', {"flow": value})

	def _onHeatingUp(self,event,value):
		self.publishEvent('printer_state_changed', {"heatingUp": value})

	def _onTemperatureChanged(self,event,value):
		self.publishEvent('temperature_changed', value)

	def _onPrintingProgressChanged(self,event,value):
		self.publishEvent('printing_progress_changed', value)

	def _onPrintCaptureInfoChanged(self,event,value):
		self.publishEvent('print_capture_info_changed',value)

	def _onPrintStarted(self,event,value):
		data = value
		data['state'] = 'started'
		self.publishEvent('printing_state_changed',data)

	def _onPrintDone(self,event,value):
		data = value
		data['state'] = 'done'
		self.publishEvent('printing_state_changed', data)

	def _onPrintFailed(self,event,value):
		data = value
		data['state'] = 'failed'
		self.publishEvent('printing_state_changed', data)

	def _onPrintCancelled(self,event,value):
		data = value
		data['state'] = 'cancelled'
		self.publishEvent('printing_state_changed', data)

	def _onPrintPaused(self,event,value):
		data = value
		data['state'] = 'paused'
		self.publishEvent('printing_state_changed', data)

	def _onPrintResumed(self,event,value):
		data = value
		data['state'] = 'resumed'
		self.publishEvent('printing_state_changed', data)

	def _onPrintingError(self,event,value):
		data = value
		data['state'] = 'printing_error'
		self.publishEvent('printing_state_changed', data)
