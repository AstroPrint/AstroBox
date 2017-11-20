# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.settings import settings

class SystemService(PluginService):
	_validEvents = ['started', 'shutting_down']

	def __init__(self):
		super(SystemService, self).__init__()

	#REQUESTS

	#write a key in config.yaml file
	def setSetting(self, data, sendResponse):
		if 'key' in data and 'value' in data:
			settings().set(data['key'], data['value'])
			settings().save()
			sendResponse({'success':'no error'})
		else:
			sendResponse('error_writing_setting',True)

	#read a key in config.yaml file
	def getSetting(self, data, sendResponse):
		if 'key' in data:
			sendResponse(settings().get(data['key']))
		else:
			sendResponse('key_setting_error',True)

	##connection
	def printerConnectionDriver(self, data, sendMessage):

		s = settings()
		pm = printerManager()
		ppm = printerProfileManager()
		connectionOptions = pm.getConnectionOptions()

		data['settings']

		if data['settings']:
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
			"serial": {
				"port": connectionOptions["portPreference"],
				"baudrate": connectionOptions["baudratePreference"],
				"portOptions": connectionOptions["ports"].items(),
				"baudrateOptions": connectionOptions["baudrates"]
			}
		})

		return

	def cameraSettings(self,data,sendMessage):
		s = settings()
		cm = cameraManager()

		if data['settings']:
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

		sendMessage(
			encoding= s.get(['camera', 'encoding']),
			size= s.get(['camera', 'size']),
			framerate= s.get(['camera', 'framerate']),
			format= s.get(['camera', 'format']),
			source= s.get(['camera', 'source']),
			video_rotation= s.getInt(['camera', 'video-rotation']),
			structure= cm.settingsStructure()
		)

		return


	def networkName(self,data,sendMessage):

		nm = networkManager()

		if data['name']:

				nm.setHostname(data['name'])

		sendMessage(name=nm.getHostname())

		return

	def networkSettings(self,data,sendMessage):
		nm = networkManager()

		sendMessage({
			'networks': nm.getActiveConnections(),
			'hasWifi': nm.hasWifi(),
			'storedWifiNetworks': nm.storedWifiNetworks()
		})

		return

	def wifiNetworks(self,data,sendMessage):
		networks = networkManager().getWifiNetworks()

		if networks:
			sendMessage(networks = networks)
		else:
			sendMessage("unable_get_wifi_networks",True)

		return

	def setWifiNetwork(self,data,sendMessage):

		if 'id' in data and 'password' in data:
			result = networkManager().setWifiNetwork(data['id'], data['password'])

			if result:
				sendMessage(jsonify(result))
			else:
				sendMessage('network_not_found',True)

		return

	def deleteStoredWiFiNetwork(self,data,sendMessage):
		nm = networkManager()

		if nm.deleteStoredWifiNetwork(data['networkId']):
			sendMessage({'success': 'no_error'})
		else:
			sendMessage("network_not_found",True)

		return

	def cameraSettings(self,data,sendMessage):
		s = settings()
		cm = cameraManager()

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
			'video_rotation': s.getInt(['camera', 'video-rotation']),
			'structure': cm.settingsStructure()
		})

		return

	##plugin

	def getAdvancedSoftwareSettings(self,data,sendMessage):
		s = settings()

		logsDir = s.getBaseFolder("logs")

		sendMessage(jsonify(
			apiKey= {
				"key": UI_API_KEY,
				"regenerate": s.getBoolean(['api','regenerate'])
			},
			serialActivated= s.getBoolean(['serial', 'log']),
			sizeLogs= sum([os.path.getsize(os.path.join(logsDir, f)) for f in os.listdir(logsDir)])
		))

		return

	def changeApiKeySettings(self,data,sendMessage):

		if data and 'regenerate' in data:
			s = settings()
			s.setBoolean(['api', 'regenerate'], data['regenerate'])

			if data['regenerate']:
				s.set(['api', 'key'], None)
			else:
				s.set(['api', 'key'], UI_API_KEY)

			s.save()

			sendMessage(jsonify())

		else:
			sendMessage('wrong_data_sent_in',True)

		return


	def resetFactorySettings(self,data,sendMessage):
		from astroprint.cloud import astroprintCloud
		from shutil import copy

		logger = logging.getLogger(__name__)
		logger.warning("Executing a Restore Factory Settings operation")

		#We log out first
		astroprintCloud().signout()

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

		#remove box-id so it's re-created on bootup
		boxIdFile = os.path.join(configFolder, "box-id")
		if os.path.exists(boxIdFile):
			os.unlink(boxIdFile)

		#remove info about users
		user_file  = s.get(["accessControl", "userfile"]) or os.path.join( configFolder, "users.yaml")
		if user_file and os.path.exists(user_file):
			os.unlink(user_file)

		logger.info("Restore completed, rebooting...")

		#We should reboot the whole device
		if softwareManager.restartServer():
			sendMessage({'success': 'no_error'})
		else:
			sendResponse("error_rebooting",True)

		return

	def checkSoftwareVersion(self,data,sendResponse):
		softwareInfo = softwareManager.checkSoftwareVersion()

		if softwareInfo:
			s = settings()
			s.set(["software", "lastCheck"], time.time())
			s.save()
			sendResponse(jsonify(softwareInfo))
		else:
			sendResponse("error_checking_update",True)

		return

	def updateSoftwareVersion(self,data,sendResponse):
		if softwareManager.updateSoftwareVersion(request.get_json()):
			sendMessage({'success': 'no_error'})
		else:
			sendResponse("error_init_update",True)

		return

	def sendLogs(self,data,sendResponse):
		if softwareManager.sendLogs(request.values.get('ticket', None), request.values.get('message', None)):
			sendMessage({'success': 'no_error'})
		else:
			sendResponse("error_sending_logs",True)

		return

	def changeSerialLogs(self,data,sendResponse):

		if data and 'active' in data:
			s = settings()
			s.setBoolean(['serial', 'log'], data['active'])
			s.save()

			printerManager().setSerialDebugLogging(data['active'])

			sendMessage({'success': 'no_error'})

		else:
			sendResponse("no_data_sent",True)

		return

	def clearLogs(self,data,sendResponse):
		if softwareManager.clearLogs():
			sendMessage({'success': 'no_error'})
		else:
			sendResponse("error_clear_logs",True)

		return

	def getSysmteInfo():
		sendResponse( softwareManager.systemInfo )

		return
