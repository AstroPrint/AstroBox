# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import re

import octoprint.util as util


from flask import request, jsonify, make_response

from octoprint.settings import settings, valid_boolean_trues
from octoprint.server import restricted_access, NO_CONTENT
from octoprint.server.api import api

from astroprint.printer.manager import printerManager 

#~~ Printer


@api.route("/printer", methods=["GET"])
def printerState():
	pm = printerManager()

	if not pm.isOperational():
		return make_response("Printer is not operational", 409)

	# process excludes
	excludes = []
	if "exclude" in request.values:
		excludeStr = request.values["exclude"]
		if len(excludeStr.strip()) > 0:
			excludes = filter(lambda x: x in ["temperature", "sd", "state"], map(lambda x: x.strip(), excludeStr.split(",")))

	result = {}

	# add temperature information
	if not "temperature" in excludes:
		result.update({"temperature": _getTemperatureData(lambda x: x)})

	# add sd information
	if not "sd" in excludes and settings().getBoolean(["feature", "sdSupport"]):
		result.update({"sd": {"ready": pm.isSdReady()}})

	# add state information
	if not "state" in excludes:
		state = pm.getCurrentData()["state"]
		result.update({"state": state})

	return jsonify(result)


#~~ Tool


@api.route("/printer/tool", methods=["POST"])
@restricted_access
def printerToolCommand():
	pm = printerManager()

	if not pm.isOperational():
		return make_response("Printer is not operational", 409)

	valid_commands = {
		"select": ["tool"],
		"target": ["targets"],
		"offset": ["offsets"],
		"extrude": ["amount"]
	}
	command, data, response = util.getJsonCommandFromRequest(request, valid_commands)
	if response is not None:
		return response

	validation_regex = re.compile("tool\d+")

	##~~ tool selection
	if command == "select":
		tool = data["tool"]
		if re.match(validation_regex, tool) is None:
			return make_response("Invalid tool: %s" % tool, 400)
		if not tool.startswith("tool"):
			return make_response("Invalid tool for selection: %s" % tool, 400)

		pm.changeTool(tool)

	##~~ temperature
	elif command == "target":
		targets = data["targets"]

		# make sure the targets are valid and the values are numbers
		validated_values = {}
		for tool, value in targets.iteritems():
			if re.match(validation_regex, tool) is None:
				return make_response("Invalid target for setting temperature: %s" % tool, 400)
			if not isinstance(value, (int, long, float)):
				return make_response("Not a number for %s: %r" % (tool, value), 400)
			validated_values[tool] = value

		# perform the actual temperature commands
		for tool in validated_values.keys():
			pm.setTemperature(tool, validated_values[tool])

	##~~ extrusion
	elif command == "extrude":
		if pm.isPrinting():
			# do not extrude when a print job is running
			return make_response("Printer is currently printing", 409)

		amount = data["amount"]
		if not isinstance(amount, (int, long, float)):
			return make_response("Not a number for extrusion amount: %r" % amount, 400)
		pm.extrude(None, amount)

	return NO_CONTENT


@api.route("/printer/tool", methods=["GET"])
def printerToolState():
	def deleteBed(x):
		data = dict(x)

		if "bed" in data.keys():
			del data["bed"]
		return data

	return jsonify(_getTemperatureData(deleteBed))


##~~ Heated bed


@api.route("/printer/bed", methods=["POST"])
@restricted_access
def printerBedCommand():
	pm = printerManager()

	if not pm.isOperational():
		return make_response("Printer is not operational", 409)

	valid_commands = {
		"target": ["target"],
		"offset": ["offset"]
	}
	command, data, response = util.getJsonCommandFromRequest(request, valid_commands)
	if response is not None:
		return response

	##~~ temperature
	if command == "target":
		target = data["target"]

		# make sure the target is a number
		if not isinstance(target, (int, long, float)):
			return make_response("Not a number: %r" % target, 400)

		# perform the actual temperature command
		pm.setTemperature("bed", target)

	return NO_CONTENT


@api.route("/printer/bed", methods=["GET"])
def printerBedState():
	def deleteTools(x):
		data = dict(x)

		for k in data.keys():
			if k.startswith("tool"):
				del data[k]
		return data

	return jsonify(_getTemperatureData(deleteTools))

@api.route("/printer/fan", methods=["POST"])
def printerFanCommand():
	pm = printerManager()

	if not pm.isOperational():
		return make_response("Printer is not operational", 409)

	valid_commands = {
		"set": ["tool", "speed"]
	}

	command, data, response = util.getJsonCommandFromRequest(request, valid_commands)
	if response is not None:
		return response

	pm.fan(data["tool"], data["speed"])

	return NO_CONTENT


##~~ Print head


@api.route("/printer/printhead", methods=["POST"])
@restricted_access
def printerPrintheadCommand():
	pm = printerManager()

	if not pm.isOperational() or pm.isPrinting():
		# do not jog when a print job is running or we don't have a connection
		return make_response("Printer is not operational or currently printing", 409)

	valid_commands = {
		"jog": [],
		"home": ["axes"]
	}
	command, data, response = util.getJsonCommandFromRequest(request, valid_commands)
	if response is not None:
		return response

	valid_axes = ["x", "y", "z"]
	##~~ jog command
	if command == "jog":
		# validate all jog instructions, make sure that the values are numbers
		validated_values = {}
		for axis in valid_axes:
			if axis in data:
				value = data[axis]
				if not isinstance(value, (int, long, float)):
					return make_response("Not a number for axis %s: %r" % (axis, value), 400)
				validated_values[axis] = value

		# execute the jog commands
		for axis, value in validated_values.iteritems():
			pm.jog(axis, value)

	##~~ home command
	elif command == "home":
		validated_values = []
		axes = data["axes"]
		for axis in axes:
			if not axis in valid_axes:
				return make_response("Invalid axis: %s" % axis, 400)
			validated_values.append(axis)

		# execute the home command
		pm.home(validated_values)

	return NO_CONTENT


##~~ SD Card


@api.route("/printer/sd", methods=["POST"])
@restricted_access
def printerSdCommand():
	if not settings().getBoolean(["feature", "sdSupport"]):
		return make_response("SD support is disabled", 404)

	pm = printerManager()

	if not pm.isOperational() or pm.isPrinting() or pm.isPaused():
		return make_response("Printer is not operational or currently busy", 409)

	valid_commands = {
		"init": [],
		"refresh": [],
		"release": []
	}
	command, data, response = util.getJsonCommandFromRequest(request, valid_commands)
	if response is not None:
		return response

	if command == "init":
		pm.initSdCard()
	elif command == "refresh":
		pm.refreshSdFiles()
	elif command == "release":
		pm.releaseSdCard()

	return NO_CONTENT


@api.route("/printer/sd", methods=["GET"])
def printerSdState():
	if not settings().getBoolean(["feature", "sdSupport"]):
		return make_response("SD support is disabled", 404)

	return jsonify(ready=printerManager().isSdReady())


##~~ Commands


@api.route("/printer/command", methods=["POST"])
@restricted_access
def printerCommand():
	pm = printerManager()

	if not pm.isOperational():
		return make_response("Printer is not operational", 409)

	if not "application/json" in request.headers["Content-Type"]:
		return make_response("Expected content type JSON", 400)

	data = request.json

	parameters = {}
	if "parameters" in data.keys():
		parameters = data["parameters"]

	commands = []
	if "command" in data.keys():
		commands = [data["command"]]
	elif "commands" in data.keys():
		commands = data["commands"]

	commandsToSend = []
	for command in commands:
		commandToSend = command
		if len(parameters) > 0:
			commandToSend = command % parameters
		commandsToSend.append(commandToSend)

	pm.commands(commandsToSend)

	return NO_CONTENT


@api.route("/printer/command/custom", methods=["GET"])
def getCustomControls():
	# TODO: document me
	customControls = settings().get(["controls"])
	return jsonify(controls=customControls)


def _getTemperatureData(filter):
	pm = printerManager()

	if not pm.isOperational():
		return make_response("Printer is not operational", 409)

	tempData = pm.getCurrentTemperatures()

	if "history" in request.values.keys() and request.values["history"] in valid_boolean_trues:
		tempHistory = pm.getTemperatureHistory()

		limit = 300
		if "limit" in request.values.keys() and unicode(request.values["limit"]).isnumeric():
			limit = int(request.values["limit"])

		history = list(tempHistory)
		limit = min(limit, len(history))

		tempData.update({
			"history": map(lambda x: filter(x), history[-limit:])
		})

	return filter(tempData)

