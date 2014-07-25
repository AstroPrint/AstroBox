# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import re
import octoprint.server

from functools import wraps

from sys import platform

from flask import make_response, request, jsonify

from octoprint.settings import settings
from octoprint.server import restricted_access, printer, NO_CONTENT, networkManager
from octoprint.server.api import api
from octoprint.printer import getConnectionOptions
from octoprint.slicers.cloud.proven_to_print import ProvenToPrintSlicer

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

@api.route('/setup/name', methods=['POST'])
@not_setup_only
def save_name():
	name = request.values.get('name', None)

	if not name or not re.search(r"^[a-zA-Z0-9\-_]+$", name):
		return make_response('Invalid Name', 400)
	else:
		if platform == "linux" or platform == "linux2":
			return make_response('Not suported', 400)
		else:
			return NO_CONTENT

@api.route('/setup/internet', methods=['GET'])
@not_setup_only
def check_internet():
	if platform == "darwin":
		return jsonify(connected = True)

	else:
		import urllib2

		try:
			urllib2.urlopen("%s/check" % settings().get(['cloudSlicer','apiHost']),timeout=1)
			return jsonify(connected = True)

		except urllib2.URLError as err: 
			pass

		networks = networkManager.getWifiNetworks()

		if networks:
			return jsonify(networks = networks, connected = False)
		else:
			return make_response("Unable to get WiFi networks", 500)

@api.route('/setup/internet', methods=['POST'])
@not_setup_only
def connect_internet():
	if "application/json" in request.headers["Content-Type"]:
		data = request.json
		result = networkManager.setWifiNetwork(data['id'], data['password'])

		if result:
			return jsonify(result)
		else:
			return ("Network %s not found" % data['id'], 404)

	return ("Invalid Request", 400)

@api.route('/setup/astroprint', methods=['GET'])
@not_setup_only
def get_astroprint_info():
	s = settings()

	email = s.get(['cloudSlicer', 'email'])

	if s.get(['cloudSlicer', "privateKey"]) and email:
		return jsonify(user=email)
	else:
		return jsonify(user=None)

@api.route('/setup/astroprint', methods=['DELETE'])
@not_setup_only
def logout_astroprint():
	s = settings()

	s.set(['cloudSlicer', "privateKey"], None)
	s.set(['cloudSlicer', "email"], None)
	s.set(['cloudSlicer', "publicKey"], None)
	s.save()

	return make_response("OK", 200)


@api.route('/setup/astroprint', methods=['POST'])
@not_setup_only
def login_astroprint():
	email = request.values.get('email', None)
	password = request.values.get('password', None)

	if email and password:
		slicer = ProvenToPrintSlicer()

		private_key = slicer.get_private_key(email, password)

		if private_key:
			public_key = slicer.get_public_key(email, private_key)

			if public_key:
				s = settings()
				s.set(["cloudSlicer", "privateKey"], private_key)
				s.set(["cloudSlicer", "publicKey"], public_key)
				s.set(["cloudSlicer", "email"], email)
				#s.setBoolean(["server", "firstRun"], False)
				s.save()
				return make_response("OK", 200)

	return make_response('Invalid Credentials', 400)

@api.route('/setup/printer', methods=['GET'])
@not_setup_only
def connection_settings():
	connectionOptions = getConnectionOptions()

	if connectionOptions:
		response = {
			"port": connectionOptions["portPreference"],
			"baudrate": connectionOptions["baudratePreference"],
			"portOptions": connectionOptions["ports"],
			"baudrateOptions": connectionOptions["baudrates"]
		}

		return jsonify(response)

	return make_response("Connection options not available", 400)

@api.route('/setup/printer', methods=['POST'])
@not_setup_only
def save_connection_settings():
	port = request.values.get('port', None)
	baudrate = request.values.get('baudrate', None)

	if port and baudrate:
		s = settings()

		s.set(["serial", "port"], port)
		s.setInt(["serial", "baudrate"], baudrate)
		s.save()

		printer.connect()
		return make_response("OK", 200)

	return make_response('Invalid Connection Settings', 400)

@api.route('/setup/done', methods=['POST'])
@not_setup_only
def set_setup_done():
	s = settings()
	s.setBoolean(['server', 'firstRun'], False)
	s.save()

	return make_response("OK", 200)
