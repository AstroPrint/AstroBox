# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import request, jsonify, make_response

from octoprint.settings import settings
from astroprint.printer import Printer
from octoprint.server import printer, restricted_access, NO_CONTENT
from octoprint.server.api import api
import octoprint.util as util


@api.route("/connection", methods=["GET"])
def connectionState():
	state, port, baudrate = printer.getCurrentConnection()
	current = {
		"state": state,
		"port": port,
		"baudrate": baudrate
	}
	return jsonify({"current": current, "options": Printer.getConnectionOptions()})


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

	if command == "connect":
		options = Printer.getConnectionOptions()
		s = settings()

		driver = None
		port = None
		baudrate = None
		if "driver" in data.keys():
			global printer 

			from astroprint.printer.manager import printerManager

			driver = data["driver"]

			printer = printerManager(driver, printer._gcodeManager)

		if "port" in data.keys():
			port = data["port"]
			if port not in options["ports"]:
				return make_response("Invalid port: %s" % port, 400)

		if "baudrate" in data.keys():
			baudrate = data["baudrate"]
			if baudrate not in options["baudrates"]:
				return make_response("Invalid baudrate: %d" % baudrate, 400)

		if "save" in data.keys() and data["save"]:

			s.set(["serial", "driver"], driver)
			s.set(["serial", "port"], port)
			s.setInt(["serial", "baudrate"], baudrate)

		if "autoconnect" in data.keys():
			s.setBoolean(["serial", "autoconnect"], data["autoconnect"])

		s.save()

		printer.connect(port=port, baudrate=baudrate)

	elif command == "disconnect":
		printer.disconnect()

	return NO_CONTENT


