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
	atm = additionalTasksManager()

	result = atm.data.copy()
	return jsonify( result )

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
