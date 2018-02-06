# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import re
import octoprint.server

from functools import wraps

from sys import platform
from requests import ConnectionError

from flask import make_response, request, jsonify
from flask_login import current_user

from octoprint.settings import settings
from octoprint.server import restricted_access, NO_CONTENT
from octoprint.server.api import api

from astroprint.cloud import astroprintCloud, AstroPrintCloudNoConnectionException
from astroprint.network.manager import networkManager
from astroprint.printer.manager import printerManager
from astroprint.printerprofile import printerProfileManager
from astroprint.plugin import pluginManager

def not_setup_only(func):
	"""
	If you decorate a view with this, it will ensure that the calls only run on
	first setup.
	"""
	@wraps(func)
	def decorated_view(*args, **kwargs):
		# if OctoPrint hasn't been set up yet, allow
		if settings().getBoolean(["server", "firstRun"]):
			return func(*args, **kwargs)
		else:
			return make_response("AstroBox is already setup", 403)
	return decorated_view

@api.route('/setup/name', methods=['GET'])
@not_setup_only
def get_name():
	return jsonify(name = networkManager().getHostname())

@api.route('/setup/name', methods=['POST'])
@not_setup_only
def save_name():
	name = request.values.get('name', None)

	if not name or not re.search(r"^[a-zA-Z0-9\-_]+$", name):
		return make_response('Invalid Name', 400)
	else:
		if platform == "linux" or platform == "linux2":
			if networkManager().setHostname(name):
				return jsonify()
			else:
				return make_response("There was an error saving the hostname", 500)
		else:
			return NO_CONTENT

@api.route('/setup/internet', methods=['GET'])
@not_setup_only
def check_internet():
	nm = networkManager()

	if nm.isAstroprintReachable():
		return jsonify(connected = True)
	else:
		networks = nm.getWifiNetworks()

		if networks:
			return jsonify(networks = networks, connected = False)
		else:
			return make_response("Unable to get WiFi networks", 500)

@api.route('/setup/internet', methods=['POST'])
@not_setup_only
def connect_internet():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json
		if 'id' in data and 'password' in data:
			result = networkManager().setWifiNetwork(data['id'], data['password'])

			if result:
				return jsonify(result)
			else:
				return make_response("Network %s not found" % data['id'], 404)

	return make_response("Invalid Request", 400)

@api.route('/setup/internet', methods=['PUT'])
@not_setup_only
def save_hotspot_option():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json

		if "hotspotOnlyOffline" in data:
			s = settings()
			s.set(['wifi', 'hotspotOnlyOffline'], data["hotspotOnlyOffline"])
			s.save()
			return jsonify()

	return make_response("Invalid Request", 400)

@api.route('/setup/astroprint', methods=['GET'])
@not_setup_only
def get_astroprint_info():
	if current_user and current_user.is_authenticated and current_user.privateKey:
		return jsonify(user=current_user.get_id())
	else:
		return jsonify(user=None)

@api.route('/setup/astroprint', methods=['DELETE'])
@not_setup_only
def logout_astroprint():
	astroprintCloud().signout()
	return make_response("OK", 200)


@api.route('/setup/astroprint', methods=['POST'])
@not_setup_only
def login_astroprint():
	email = request.values.get('email', None)
	password = request.values.get('password', None)

	if email and password:
		ap = astroprintCloud()

		try:
			if ap.signin(email, password):
				return make_response("OK", 200)

		except (AstroPrintCloudNoConnectionException, ConnectionError):
			return make_response("AstroPrint.com can't be reached", 503)

	return make_response('Invalid Credentials', 400)

@api.route('/setup/printer', methods=['GET'])
@not_setup_only
def connection_settings():
	connectionOptions = printerManager().getConnectionOptions()

	if connectionOptions:

		plugins = pluginManager().getPluginsByProvider('printerComms')

		driverChoices = { ("plugin:%s" % k) : plugins[k].definition['name'] for k in plugins }

		driverChoices.update({
			'marlin': 'GCODE - Marlin / Repetier Firmware',
			's3g': 'X3G - Sailfish / Makerbot Firmware'
		})

		response = {
			"driver": printerProfileManager().data['driver'],
			"driverChoices": driverChoices,
			"port": connectionOptions["portPreference"],
			"baudrate": connectionOptions["baudratePreference"],
			"portOptions": connectionOptions["ports"].items(),
			"baudrateOptions": connectionOptions["baudrates"]
		}

		return jsonify(response)

	return make_response("Connection options not available", 400)

@api.route('/setup/printer', methods=['POST'])
@not_setup_only
def save_connection_settings():
	port = request.values.get('port', None)
	baudrate = request.values.get('baudrate', None)
	driver = request.values.get('driver', None)

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

		return make_response("OK", 200)

	return make_response('Invalid Connection Settings', 400)

@api.route('/setup/printer/profile', methods=['POST'])
@not_setup_only
def save_printer_profile_settings():
	driver = request.values.get('driver', None)

	if driver:
		pp = printerProfileManager()
		pp.set({'driver': driver})
		pp.save()

		return make_response("OK", 200)

	return make_response('Invalid Connection Settings', 400)

@api.route('/setup/done', methods=['POST'])
@not_setup_only
def set_setup_done():
	s = settings()
	s.setBoolean(['server', 'firstRun'], False)
	s.save()

	return make_response("OK", 200)
