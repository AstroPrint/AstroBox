# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import jsonify, request, make_response

from octoprint.server.api import api
from octoprint.server import restricted_access

from astroprint.additionaltasks import additionalTasksManager

@api.route('/additional-tasks', methods=['GET'])
@restricted_access
def additionalTasks():
	return jsonify( additionalTasksManager().data )

@api.route('/additional-tasks', methods=['POST'])
@restricted_access
def additionalTasksCreate():
	if not "file" in request.files.keys():
		return make_response("No file included", 400)

	file = request.files["file"]

	atm = additionalTasksManager()
	r = atm.checkTaskFile(file)

	if 'error' in r:
		return make_response(r['error'], 500)
	else:
		return jsonify(r)

@api.route("/additional-tasks", methods=["DELETE"])
@restricted_access
def deleteTask():
	data = request.json
	tId = data.get('id', None)

	if tId:
		atm = additionalTasksManager()
		r = atm.removeTask(tId)

		if 'error' in r:
			error = r['error']

			if error == 'not_found':
				return make_response('Not Found', 404)
			else:
				return make_response(error, 500)

		else:
			return jsonify(r)

	return make_response('Invalid Request', 400)

@api.route("/additional-tasks/install", methods=["POST"])
@restricted_access
def installTask():
	data = request.json
	file = data.get('file', None)
	if file:
		atm = additionalTasksManager()
		if atm.installFile(file):
			return jsonify()
		else:
			return make_response('Unable to Install', 500)

	return make_response('Invalid Request', 400)
