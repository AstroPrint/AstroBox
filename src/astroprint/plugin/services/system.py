# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import time
import os
import sarge
import threading

from . import PluginService
from octoprint.settings import settings
from octoprint.events import Events

from astroprint.printer.manager import printerManager

from astroprint.printerprofile import printerProfileManager
from astroprint.additionaltasks import additionalTasksManager
from astroprint.maintenancemenu import maintenanceMenuManager
from astroprint.manufacturerpkg import manufacturerPkgManager
from astroprint.camera import cameraManager
from astroprint.network.manager import networkManager
from octoprint.server import softwareManager, UI_API_KEY
from astroprint.boxrouter import boxrouterManager
#from astroprint.plugin import pluginManager

class SystemService(PluginService):
	_validEvents = ['started', 'shutting_down', 'software_update']

	def __init__(self):
		super(SystemService, self).__init__()
		self._eventManager.subscribe(Events.SOFTWARE_UPDATE, self._onSoftwareUpdate)

	#EVENT
	def _onSoftwareUpdate(self,event,value):
		self.publishEvent('software_update', value)

	#REQUESTS

	#write a key in config.yaml file
	def setSetting(self, data, sendResponse=None):
		if 'key' in data and 'value' in data:
			settings().set(data['key'], data['value'])
			settings().save()
			if sendResponse:
				sendResponse({'success':'no error'})
			return True

		else:
			if sendResponse:
				sendResponse('error_writing_setting',True)

			return False

	#read a key in config.yaml file
	def getSetting(self, data, sendResponse=None):
		if 'key' in data:
			value = settings().get(data['key'])
			if sendResponse:
				sendResponse(value)

			return value
		else:
			if sendResponse:
				sendResponse('key_setting_error',True)

			return False

	##connection
	def printerConnectionDriver(self, data, sendMessage):

		s = settings()
		pm = printerManager()
		ppm = printerProfileManager()
		connectionOptions = pm.getConnectionOptions()

		if data and data['settings']:
			if "serial" in data.keys():
				if "port" in data["serial"].keys(): s.set(["serial", "port"], data["serial"]["port"])
				if "baudrate" in data["serial"].keys(): s.setInt(["serial", "baudrate"], data["serial"]["baudrate"])

			s.save()

		driverName = ppm.data['driver']
		driverInfo = ppm.driverChoices().get(driverName)
		if driverInfo:
			driverName = driverInfo['name']

		sendMessage({
			"driver": ppm.data['driver'],
			"driverName": driverName,
			"fileFormat": pm.fileManager.fileFormat,
			"serial": {
				"port": connectionOptions["portPreference"],
				"baudrate": connectionOptions["baudratePreference"],
				"portOptions": connectionOptions["ports"],
				"baudrateOptions": connectionOptions["baudrates"]
			}
		})

	def saveConnectionSettings(self,data,sendResponse):
		port = data['port']
		baudrate = data['baudrate']
		driver = data['driver']

		if port:
			s = settings()

			s.set(["serial", "port"], port)

			if baudrate:
				s.setInt(["serial", "baudrate"], baudrate)

			s.save()

			pp = printerProfileManager()
			pp.set({'driver': driver})
			pp.save()

			printerManager().connect(port, baudrate)

			sendResponse({'success': 'no_error'})
			return

		sendResponse('invalid_printer_connection_settings',True)

	def connectionCommand(self, data, sendResponse):
		valid_commands = {
			"connect": ["autoconnect"],
			"disconnect": [],
			"reconnect": []
		}

		command = data['command']

		pm = printerManager()

		if command in ["connect", "reconnect"]:
			s = settings()

			driver = None
			port = None
			baudrate = None

			options = pm.getConnectionOptions()

			if "port" in data:
				port = data["port"]
				if port not in options["ports"]:
					if port is None:
						port = "None"
					sendResponse("invalid_port_" + port,True)
					return

			if "baudrate" in data and data['baudrate']:
				baudrate = int(data["baudrate"])
				if baudrate:
					baudrates = options["baudrates"]
					if baudrates and baudrate not in baudrates:
						sendResponse("invalid_baudrate_" +  baudrate,True)
						return

				else:
					sendResponse("baudrate_null",True)
					return

			if "save" in data and data["save"]:
				s.set(["serial", "port"], port)
				s.setInt(["serial", "baudrate"], baudrate)

			if "autoconnect" in data:
				s.setBoolean(["serial", "autoconnect"], data["autoconnect"])

			s.save()

			if command == "connect":
				pm.connect(port, baudrate)
			elif command == "reconnect":
				pm.reConnect(port, baudrate)

		elif command == "disconnect":
			pm.disconnect()

		sendResponse({'success':'no error'})

	#profile
	def printerProfile(self, data, sendMessage):

		ppm = printerProfileManager()

		if data:
			if 'driverChoices' in data:
				del data['driverChoices']

			ppm.set(data)
			ppm.save()

			sendMessage({'success': 'no_error'})
		else:

			result = ppm.data.copy()
			result.update( {"driverChoices": ppm.driverChoices()} )

			sendMessage( result )

	def printingInfo(self, data, sendMessage):
		pm = printerManager()
		result = {}

		if pm.isPrinting() or pm.isPaused():

			# PRINTING INFO
			currentFile = pm.selectedFile
			fileName = currentFile["filename"]

			result = pm.getFileInfo(fileName)

			# PRINTING PROGRESS
			printTime = pm.getPrintTime()
			progress = pm.getPrintProgress()
			estimatedTimeLeft = None

			if pm._estimatedPrintTime:
				if printTime and progress:
					if progress < 1.0:
						estimatedTimeLeft = pm._estimatedPrintTime * ( 1.0 - progress )
						elaspedTimeVariance = printTime - ( pm._estimatedPrintTime - estimatedTimeLeft )
						adjustedEstimatedTime = pm._estimatedPrintTime + elaspedTimeVariance
						estimatedTimeLeft = ( adjustedEstimatedTime * ( 1.0 -  progress) ) / 60
					else:
						estimatedTimeLeft = 0

				else:
					estimatedTimeLeft = pm._estimatedPrintTime / 60

			value = pm._formatPrintingProgressData(progress, pm.getPrintFilepos(), printTime, estimatedTimeLeft, pm.getCurrentLayer())
			result['progress'] = value

		sendMessage(result)

	def saveTempPreset(self, data, sendMessage):
		ppm = printerProfileManager()

		if data:
			id = ppm.createTempPreset(data['name'], data['nozzle_temp'], data['bed_temp'])
			sendMessage( id )

	def additionalTasks(self, data ,sendMessage):
		sendMessage( additionalTasksManager().data )

	def maintenanceMenu(self, data ,sendMessage):
		mmenu = maintenanceMenuManager()
		result = mmenu.data

		sendMessage(result)

	def manufacturerPackage(self, data ,sendMessage):
		manPackage = manufacturerPkgManager()
		result = {}

		if data:
			if "parameter" in data:
				if data['parameter'] == "strings":
					lang = "en"
					if "language" in data:
						lang = data['language']
					# Get strings from passed keys
					if "keys" in data:
						keys = data["keys"]
						for k in keys:
							result[k]= manPackage.getString(k,lang)
					# Get all the strings if no keys passed
					else:
						strings = manPackage.data.get("strings")
						for s in strings:
							result[s]= manPackage.getString(s,lang)
				else:
					result = manPackage.data.get(data["parameter"])
		else:
			result = manPackage.data

		sendMessage(result)

	def refreshPluggedCamera(self, data, sendMessage):
		cm = cameraManager()
		sendMessage({"camera_plugged": cm.reScan()})

	def isResolutionSupported(self, size, sendMessage):
		cm = cameraManager()
		sendMessage({"isResolutionSupported": cm.isResolutionSupported(size)})

	def cameraSettings(self, data, sendMessage):
		s = settings()
		cm = cameraManager()

		if data:
			if "source" in data:
				s.set(['camera', 'source'], data['source'])

			if "size" in data:
				s.set(['camera', 'size'], data['size'])

			if "encoding" in data:
				s.set(['camera', 'encoding'], data['encoding'])

			if "format" in data:
				s.set(['camera', 'format'], data['format'])

			if "framerate" in data:
				s.set(['camera', 'framerate'], data['framerate'])

			if "video_rotation" in data:
				s.set(['camera', 'video-rotation'], int(data['video_rotation']))

			s.save()

			cm.settingsChanged({
				'size': s.get(['camera', 'size']),
				'encoding': s.get(['camera', 'encoding']),
				'framerate': s.get(['camera', 'framerate']),
				'source': s.get(['camera', 'source']),
				'format': s.get(['camera', 'format']),
				'video_rotation': s.get(['camera', 'video-rotation'])
			})

		sendMessage({
			'encoding': s.get(['camera', 'encoding']),
			'size': s.get(['camera', 'size']),
			'framerate': s.get(['camera', 'framerate']),
			'format': s.get(['camera', 'format']),
			'source': s.get(['camera', 'source']),
			'video_rotation': str(s.getInt(['camera', 'video-rotation'])),
			'structure': cm.settingsStructure()
		})

	def getAdvancedSoftwareSettings(self, data, sendMessage):
		s = settings()

		logsDir = s.getBaseFolder("logs")

		sendMessage({
			'apiKey': {
				"key": UI_API_KEY,
				"regenerate": s.getBoolean(['api','regenerate'])
			},
			'serialActivated': s.getBoolean(['serial', 'log']),
			'sizeLogs': sum([os.path.getsize(os.path.join(logsDir, f)) for f in os.listdir(logsDir)])
		})

	def changeApiKeySettings(self, data, sendMessage):

		if data and 'regenerate' in data:
			s = settings()
			s.setBoolean(['api', 'regenerate'], data['regenerate'])

			if data['regenerate']:
				s.set(['api', 'key'], None)
			else:
				s.set(['api', 'key'], UI_API_KEY)

			s.save()

			sendMessage({'success': 'no_error'})

		else:
			sendMessage('wrong_data_sent_in',True)

	def resetFactorySettings(self, data, sendMessage):
		from astroprint.cloud import astroprintCloud
		from shutil import copy

		try:

			#astroprintCloud().signout()
			astroprintCloud().remove_logged_user()

			logger = logging.getLogger(__name__)
			logger.warning("Executing a Restore Factory Settings operation")

			s = settings()

			#empty all folders
			def emptyFolder(folder):
				if folder and os.path.exists(folder):
					for f in os.listdir(folder):
						p = os.path.join(folder, f)
						try:
							if os.path.isfile(p):
								os.unlink(p)
						except Exception, e:
							pass

			emptyFolder(s.get(['folder', 'uploads']) or s.getBaseFolder('uploads'))
			emptyFolder(s.get(['folder', 'timelapse']) or s.getBaseFolder('timelapse'))
			emptyFolder(s.get(['folder', 'timelapse_tmp']) or s.getBaseFolder('timelapse_tmp'))
			emptyFolder(s.get(['folder', 'virtualSd']) or s.getBaseFolder('virtualSd'))

			networkManager().forgetWifiNetworks()

			configFolder = s.getConfigFolder()

			#replace config.yaml with config.factory
			config_file = s._configfile
			config_factory = os.path.join(configFolder, "config.factory")
			if config_file and os.path.exists(config_file):
				if os.path.exists(config_factory):
					copy(config_factory, config_file)
				else:
					os.unlink(config_file)

			#replace printer-profile.yaml with printer-profile.factory
			p_profile_file = os.path.join(configFolder, "printer-profile.yaml")
			p_profile_factory = os.path.join(configFolder, "printer-profile.factory")
			if os.path.exists(p_profile_file):
				if os.path.exists(p_profile_factory):
					copy(p_profile_factory, p_profile_file)
				else:
					os.unlink(p_profile_file)

			#remove info about users
			user_file  = s.get(["accessControl", "userfile"]) or os.path.join( configFolder, "users.yaml")
			if user_file and os.path.exists(user_file):
				os.unlink(user_file)

			logger.info("Restore completed, rebooting...")

			#We should reboot the whole device
			if softwareManager.restartServer():
				sendMessage({'success': 'no_error'})
			else:
				sendMessage("error_rebooting",True)

		except Exception as e:
			self._logger.error('unsuccessfully factory settings restored', exc_info = True)
			sendMessage("error_restoring_factory_settings",True)

	def softwareVersion(self,data,sendResponse):
		sendResponse(softwareManager.versionString)

	def getCurrentVersions(self,data,sendResponse):
		sendResponse(softwareManager.data)

	def shouldCheckForNew(self,data,sendResponse):
		softwareCheckInterval = 86400 #1 day
		s = settings()
		sendResponse(s.get(["software", "lastCheck"]) < ( time.time() - softwareCheckInterval ))

	def checkSoftwareVersion(self,data,sendResponse):
		softwareInfo = softwareManager.checkSoftwareVersion()

		if softwareInfo:
			s = settings()
			s.set(["software", "lastCheck"], time.time())
			s.save()
			sendResponse(softwareInfo)
		else:
			sendResponse("error_checking_update",True)

	def updateSoftwareVersion(self,data,sendResponse):
		if 'release_ids' in data:
			if softwareManager.updateSoftware(data['release_ids']):
				sendResponse({'success': 'no_error'})
				return

		sendResponse("error_init_update", True)

	def sendLogs(self,data,sendResponse):
		if softwareManager.sendLogs(request.values.get('ticket', None), request.values.get('message', None)):
			sendResponse({'success': 'no_error'})
		else:
			sendResponse("error_sending_logs",True)

	def changeSerialLogs(self,data,sendResponse):

		if data and 'active' in data:
			s = settings()
			s.setBoolean(['serial', 'log'], data['active'])
			s.save()

			printerManager().setSerialDebugLogging(data['active'])
			sendResponse({'success': 'no_error'})

		else:
			sendResponse("no_data_sent",True)

	def clearLogs(self,data,sendResponse):
		if softwareManager.clearLogs():
			sendResponse({'success': 'no_error'})
		else:
			sendResponse("error_clear_logs",True)

	def performSystemAction(self,action,sendResponse):
		available_actions = settings().get(["system", "actions"])
		logger = logging.getLogger(__name__)

		for availableAction in available_actions:
			if availableAction["action"] == action:
				command = availableAction["command"]
				if command:
					logger.info("Performing command: %s" % command)

					def executeCommand(command, logger):
						time.sleep(0.5) #add a small delay to make sure the response is sent
						try:
							p = sarge.run(command, stderr=sarge.Capture())
							if p.returncode != 0:
								returncode = p.returncode
								stderr_text = p.stderr.text
								logger.warn("Command failed with return code %i: %s" % (returncode, stderr_text))
								sendResponse({'success': False})
							else:
								logger.info("Command executed sucessfully")
								sendResponse({'success': True})

						except Exception, e:
							logger.warn("Command failed: %s" % e)

					executeThread = threading.Thread(target=executeCommand, args=(command, logger))
					executeThread.start()

				else:
					logger.warn("Action %s is misconfigured" % action)
					sendResponse('action_not_configured', True)

				return

		logger.warn("No suitable action in config for: %s" % action)
		sendResponse('no_command', True)

	def getDeviceId(self, data=None, sendResponse=None):
		boxId = boxrouterManager().boxId
		if sendResponse:
			sendResponse(boxId)

		return boxId

	def restartServer(self, data=None, sendResponse=None):
		#We should reboot the whole device
		if softwareManager.restartServer():
			sendResponse({'success': 'no_error'})
		else:
			sendResponse("error_restarting",True)
