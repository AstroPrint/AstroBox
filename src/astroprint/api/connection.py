# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import octoprint.util as util

from flask import request, jsonify, make_response

from octoprint.settings import settings
from octoprint.server import restricted_access, NO_CONTENT
from octoprint.server.api import api

from astroprint.printer.manager import printerManager



@api.route("/connection", methods=["GET"])
def connectionState():
	pm = printerManager()

	state, port, baudrate = pm.getCurrentConnection()
	current = {
		"state": state,
		"port": port,
		"baudrate": baudrate
	}
	return jsonify({"current": current, "options": pm.getConnectionOptions()})


@api.route("/connection", methods=["POST"])
@restricted_access
def connectionCommand():
	valid_commands = {
		"connect": ["autoconnect"],
		"disconnect": []
	}

	command, data, response = util.getJsonCommandFromRequest(request, valid_commands)
	if response is not None:
		return response

	pm = printerManager()

	if command == "connect":
		s = settings()

		driver = None
		port = None
		baudrate = None

		options = pm.getConnectionOptions()

		if "port" in data:
			port = data["port"]
			if port not in options["ports"]:
				return make_response("Invalid port: %s" % port, 400)

		if "baudrate" in data:
			baudrate = data["baudrate"]
			baudrates = options["baudrates"]
			if baudrates and baudrate not in baudrates:
				return make_response("Invalid baudrate: %d" % baudrate, 400)

		if "save" in data and data["save"]:
			s.set(["serial", "port"], port)
			s.setInt(["serial", "baudrate"], baudrate)

		if "autoconnect" in data:
			s.setBoolean(["serial", "autoconnect"], data["autoconnect"])

		s.save()

		pm.connect(port=port, baudrate=baudrate)

	elif command == "disconnect":
		pm.disconnect()

	return NO_CONTENT


