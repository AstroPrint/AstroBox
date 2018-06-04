# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import os
import time
import json

from flask import request, abort, jsonify, make_response

from octoprint.settings import settings
from astroprint.printer.manager import printerManager
from astroprint.network.manager import networkManager
from astroprint.camera import cameraManager
from astroprint.plugin import pluginManager
from astroprint.printerprofile import printerProfileManager

from octoprint.server import restricted_access, admin_permission, softwareManager, UI_API_KEY
from octoprint.server.api import api

@api.route("/settings/printer", methods=["GET", "POST"])
def handlePrinterSettings():
	s = settings()
	pm = printerManager()
	ppm = printerProfileManager()
	connectionOptions = pm.getConnectionOptions()

	if request.method == "POST":
		if "application/json" in request.headers["Content-Type"]:
			data = request.json

			if "serial" in data.keys():
				if "port" in data["serial"].keys(): s.set(["serial", "port"], data["serial"]["port"])
				if "baudrate" in data["serial"].keys(): s.setInt(["serial", "baudrate"], data["serial"]["baudrate"])

			s.save()

	driverName = ppm.data['driver']
	driverInfo = ppm.driverChoices().get(driverName)
	if driverInfo:
		driverName = driverInfo['name']

	return jsonify({
		"driver": ppm.data['driver'],
		"driverName": driverName,
		"serial": {
			"port": connectionOptions["portPreference"],
			"baudrate": connectionOptions["baudratePreference"],
			"portOptions": connectionOptions["ports"].items(),
			"baudrateOptions": connectionOptions["baudrates"]
		}
	})

@api.route("/settings/network/name", methods=["GET", "POST"])
@restricted_access
def handleNetworkName():
	nm = networkManager()

	if request.method == "POST":
		if "application/json" in request.headers["Content-Type"]:
			data = request.json

			nm.setHostname(data['name'])

		else:
			return ("Invalid Request", 400)

	return jsonify(name=nm.getHostname())

@api.route("/settings/network/wifi-networks", methods=["GET"])
#@restricted_access
def getWifiNetworks():
	networks = networkManager().getWifiNetworks()

	if networks:
		return jsonify(networks = networks)
	else:
		return jsonify({'message': "Unable to get WiFi networks"})

@api.route("/settings/network", methods=["GET"])
#@restricted_access
def getNetworkSettings():
	nm = networkManager()

	return jsonify({
		'networks': nm.getActiveConnections(),
		'hasWifi': nm.hasWifi(),
		'storedWifiNetworks': nm.storedWifiNetworks()
	})

@api.route("/settings/network/stored-wifi/<string:networkId>", methods=["DELETE"])
@restricted_access
def deleteStoredWiFiNetwork(networkId):
	nm = networkManager()

	if nm.deleteStoredWifiNetwork(networkId):
		return jsonify()
	else:
		return ("Network Not Found", 404)

@api.route("/settings/network/active", methods=["POST"])
#@restricted_access
def setWifiNetwork():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json
		if 'id' in data and 'password' in data:
			result = networkManager().setWifiNetwork(data['id'], data['password'])

			if result:
				return jsonify(result)
			else:
				return ("Network %s not found" % data['id'], 404)

	return ("Invalid Request", 400)

@api.route("/settings/network/hotspot", methods=["GET", "POST", "PUT", "DELETE"])
@restricted_access
def handleWifiHotspot():
	nm = networkManager()

	if request.method == "GET":
		return jsonify({
			'hotspot': {
				'active': nm.isHotspotActive(),
				'name': nm.getHostname(),
				'hotspotOnlyOffline': settings().getBoolean(['wifi', 'hotspotOnlyOffline'])
			} if nm.isHotspotable() else False
		})

	elif request.method == "PUT":
		if "application/json" in request.headers["Content-Type"]:
			data = request.json

			if "hotspotOnlyOffline" in data:
				s = settings()
				s.setBoolean(['wifi', 'hotspotOnlyOffline'], data["hotspotOnlyOffline"])
				s.save()
				return jsonify()

		return ("Invalid Request", 400)

	elif request.method == "DELETE":
		result = networkManager().stopHotspot()

		if result is True:
			return jsonify()
		else:
			return (result, 500)

	else: #POST
		result = nm.startHotspot()

		if result is True:
			return jsonify()
		else:
			return (result, 500)

@api.route("/settings/camera", methods=["GET", "POST"])
@restricted_access
def cameraSettings():
	s = settings()
	cm = cameraManager()

	if request.method == 'POST':
		if "application/json" in request.headers["Content-Type"]:
			data = request.json

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

	return jsonify(
		encoding= s.get(['camera', 'encoding']),
		size= s.get(['camera', 'size']),
		framerate= s.get(['camera', 'framerate']),
		format= s.get(['camera', 'format']),
		source= s.get(['camera', 'source']),
		video_rotation= s.getInt(['camera', 'video-rotation']),
		structure= cm.settingsStructure()
	)

@api.route("/settings/software/plugins", methods=["GET"])
@restricted_access
def getSoftwarePlugins():
	pm = pluginManager()

	response = []

	for pId, p in pm.plugins.iteritems():
		response.append({
			'id': p.pluginId,
			'name': p.name,
			'version': p.version,
			'can_remove': not p.systemPlugin,
			'verified': p.verified
		})

	r = make_response(json.dumps(response), 200)
	r.headers['Content-Type'] = 'application/json'

	return r

@api.route("/settings/software/plugins", methods=["POST"])
@restricted_access
def uploadSoftwarePlugin():
	if not "file" in request.files.keys():
		return make_response("No file included", 400)

	file = request.files["file"]

	pm = pluginManager()
	r = pm.checkFile(file)

	if 'error' in r:
		return make_response(r['error'], 500)
	else:
		return jsonify(r)

@api.route("/settings/software/plugins", methods=["DELETE"])
@restricted_access
def removeSoftwarePlugin():
	data = request.json
	pId = data.get('id', None)

	if pId:
		pm = pluginManager()
		r = pm.removePlugin(pId)

		if 'error' in r:
			error = r['error']

			if error == 'not_found':
				return make_response('Not Found', 404)
			else:
				return make_response(error, 500)

		else:
			return jsonify(r)

	return make_response('Invalid Request', 400)

@api.route("/settings/software/plugins/install", methods=["POST"])
@restricted_access
def installSoftwarePlugin():
	data = request.json
	file = data.get('file', None)
	if file:
		pm = pluginManager()
		if pm.installFile(file):
			return jsonify()
		else:
			return make_response('Unable to Install', 500)

	return make_response('Invalid Request', 400)

@api.route("/settings/software/license", methods=["GET"])
@restricted_access
def getLicenseInfo():
	pm = pluginManager()
	lcnMgr = pm.getPlugin('com.astroprint.astrobox.plugins.lcnmgr')

	if lcnMgr and lcnMgr.validLicense:
		return jsonify({
			'is_valid': True,
			'issuer': lcnMgr.issuerName,
			'expires': lcnMgr.expires,
			'license_id': lcnMgr.licenseId
		});

	return jsonify({'is_valid': False})

@api.route("/settings/software/advanced", methods=["GET"])
@restricted_access
def getAdvancedSoftwareSettings():
	s = settings()

	logsDir = s.getBaseFolder("logs")

	return jsonify(
		apiKey= {
			"key": UI_API_KEY,
			"regenerate": s.getBoolean(['api','regenerate'])
		},
		serialActivated= s.getBoolean(['serial', 'log']),
		sizeLogs= sum([os.path.getsize(os.path.join(logsDir, f)) for f in os.listdir(logsDir)]),
		updateChannel= s.getInt(['software', 'channel'])
	)

@api.route("/settings/software/advanced/apikey", methods=["PUT"])
@restricted_access
def changeApiKeySettings():
	data = request.json

	if data and 'regenerate' in data:
		s = settings()
		s.setBoolean(['api', 'regenerate'], data['regenerate'])

		if data['regenerate']:
			s.set(['api', 'key'], None)
		else:
			s.set(['api', 'key'], UI_API_KEY)

		s.save()

		return jsonify()

	else:
		return ("Wrong data sent in.", 400)

@api.route("/settings/software/advanced/update-channel", methods=["PUT"])
@restricted_access
def changeUpdateChannelSettings():
	data = request.json

	if data and 'channel' in data:
		s = settings()
		s.setInt(['software', 'channel'], data['channel'])
		s.save()

		return jsonify()

	else:
		return ("Wrong data sent in.", 400)

@api.route("/settings/software/settings", methods=["DELETE"])
@restricted_access
def resetFactorySettings():
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

	#remove info about users
	user_file  = s.get(["accessControl", "userfile"]) or os.path.join( configFolder, "users.yaml")
	if user_file and os.path.exists(user_file):
		os.unlink(user_file)

	logger.info("Restore completed, rebooting...")

	#We should reboot the whole device
	if softwareManager.restartServer():
		return jsonify()
	else:
		return ("There was an error rebooting.", 500)

@api.route("/settings/software/check", methods=['GET'])
@restricted_access
def checkSoftwareVersion():
	softwareInfo = softwareManager.checkSoftwareVersion()

	if softwareInfo:
		s = settings()
		s.set(["software", "lastCheck"], int(time.time()))
		s.save()

		return jsonify(softwareInfo)
	else:
		return ("There was an error checking for new software.", 400)

@api.route("/settings/software/update", methods=['POST', 'DELETE'])
@restricted_access
def updateSoftwareVersion():
	if request.method == 'DELETE':
		softwareManager.resetUpdate()
		return jsonify()

	else:
		data = request.get_json()

		if 'release_ids' in data:
			if softwareManager.updateSoftware(data['release_ids']):
				return jsonify()
			else:
				return ("Unable to update", 500)
		else:
			return ("Invalid data", 400)

@api.route("/settings/software/restart", methods=['POST'])
@restricted_access
def restartServer():
	if softwareManager.restartServer():
		return jsonify();
	else:
		return ("There was an error trying to restart the server.", 400)

@api.route("/settings/software/logs", methods=['POST'])
@restricted_access
def sendLogs():
	if softwareManager.sendLogs(request.values.get('ticket', None), request.values.get('message', None)):
		return jsonify();
	else:
		return ("There was an error trying to send your logs.", 500)

@api.route("/settings/software/logs/serial", methods=['PUT'])
@restricted_access
def changeSerialLogs():
	data = request.json

	if data and 'active' in data:
		s = settings()
		s.setBoolean(['serial', 'log'], data['active'])
		s.save()

		printerManager().setSerialDebugLogging(data['active'])

		return jsonify();

	else:
		return ("Wrong data sent in.", 400)

@api.route("/settings/software/logs", methods=['DELETE'])
@restricted_access
def clearLogs():
	if softwareManager.clearLogs():
		return jsonify();
	else:
		return ("There was an error trying to clear your logs.", 500)

@api.route("/settings/software/system-info", methods=['GET'])
@restricted_access
def getSysmteInfo():
	return jsonify( softwareManager.systemInfo )

@api.route("/settings/software/versions", methods=['GET'])
@restricted_access
def getCurrentVersions():
	return jsonify( softwareManager.data )
