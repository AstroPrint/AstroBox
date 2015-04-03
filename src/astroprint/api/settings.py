# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from flask import request, abort, jsonify, make_response

from octoprint.settings import settings
from octoprint.printer import getConnectionOptions

from octoprint.server import restricted_access, admin_permission, networkManager, softwareManager
from octoprint.server.api import api

@api.route("/settings/printer", methods=["GET"])
def getSettings():
	s = settings()

	connectionOptions = getConnectionOptions()

	return jsonify({
		"serial": {
			"port": connectionOptions["portPreference"],
			"baudrate": connectionOptions["baudratePreference"],
			"portOptions": connectionOptions["ports"].items(),
			"baudrateOptions": connectionOptions["baudrates"]
		}
	})


@api.route("/settings/printer", methods=["POST"])
@restricted_access
def setSettings():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json
		s = settings()

		if "serial" in data.keys():
			if "port" in data["serial"].keys(): s.set(["serial", "port"], data["serial"]["port"])
			if "baudrate" in data["serial"].keys(): s.setInt(["serial", "baudrate"], data["serial"]["baudrate"])

		s.save()

	return getSettings()

@api.route("/settings/internet/wifi-networks", methods=["GET"])
@restricted_access
def getWifiNetworks():
	networks = networkManager.getWifiNetworks()

	if networks:
		return jsonify(networks = networks)
	else:
		return jsonify({'message': "Unable to get WiFi networks"})

@api.route("/settings/internet", methods=["GET"])
@restricted_access
def getInternetSettings():
	isHotspotable = networkManager.isHotspotable()

	return jsonify({
		'networks': networkManager.getActiveConnections(),
		'hasWifi': bool(networkManager.getWifiDevice()),
		'hotspot': {
			'active': networkManager.isHotspotActive(),
			'name': networkManager.getHostname(),
			'hotspotOnlyOffline': settings().getBoolean(['wifi', 'hotspotOnlyOffline'])	
		} if isHotspotable else False
	})

@api.route("/settings/internet/active", methods=["POST"])
@restricted_access
def setWifiNetwork():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json
		result = networkManager.setWifiNetwork(data['id'], data['password'])

		if result:
			return jsonify(result)
		else:
			return ("Network %s not found" % data['id'], 404)

	return ("Invalid Request", 400)

@api.route("/settings/internet/hotspot", methods=["POST"])
@restricted_access
def startWifiHotspot():
	result = networkManager.startHotspot()

	if result is True:
		return jsonify()
	else:
		return (result, 500)

@api.route("/settings/internet/hotspot", methods=["PUT"])
@restricted_access
def changeWifiHotspot():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json

		if "hotspotOnlyOffline" in data:
			s = settings()
			s.setBoolean(['wifi', 'hotspotOnlyOffline'], data["hotspotOnlyOffline"])
			s.save()
			return jsonify()

	return ("Invalid Request", 400)

@api.route("/settings/internet/hotspot", methods=["DELETE"])
@restricted_access
def stopWifiHotspot():
	result = networkManager.stopHotspot()

	if result is True:
		return jsonify()
	else:
		return (result, 500)

@api.route("/settings/software/settings", methods=["DELETE"])
@restricted_access
def resetFactorySettings():
	import os

	from astroprint.cloud import astroprintCloud

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
	emptyFolder(s.get(['folder', 'watched']) or s.getBaseFolder('watched'))

	settings_dir = s.settings_dir
	#remove info about users
	user_file = s.get(["accessControl", "userfile"]) or os.path.join(settings_dir, "users.yaml")
	if user_file and os.path.exists(user_file):
		os.unlink(user_file)

	#replace config.yaml with config.factory
	config_file = s._configfile
	os.unlink(config_file)

	s._config = {}
	s.load(migrate=False)

	networkManager.forgetWifiNetworks()

	return jsonify()

@api.route("/settings/software/check", methods=['GET'])
@restricted_access
def checkSoftwareVersion():
	softwareInfo = softwareManager.checkSoftwareVersion()

	if softwareInfo:
		return jsonify(softwareInfo);
	else:
		return ("There was an error checking for new software.", 400)

@api.route("/settings/software/update", methods=['POST'])
@restricted_access
def updateSoftwareVersion():
	if softwareManager.updateSoftwareVersion(request.get_json()):
		return jsonify();
	else:
		return ("There was an error initiating update.", 400)

@api.route("/settings/software/restart", methods=['POST'])
@restricted_access
def restartServer():
	if softwareManager.restartServer():
		return jsonify();
	else:
		return ("There was an error trying to restart the server.", 400)