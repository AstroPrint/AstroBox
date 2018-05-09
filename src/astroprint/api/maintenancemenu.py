# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import jsonify, request, make_response

from octoprint.server.api import api
from octoprint.server import restricted_access

from astroprint.maintenancemenu import maintenanceMenuManager

@api.route('/maintenance-menu', methods=['GET'])
@restricted_access
def maintenanceMenu():
	mmenu = maintenanceMenuManager()

	result = mmenu.data
	return jsonify( result )

@api.route('/maintenance-menu', methods=['POST'])
@restricted_access
def maintenanceMenuCreate():
	if not "file" in request.files.keys():
		return make_response("No file included", 400)

	file = request.files["file"]

	mmenu = maintenanceMenuManager()
	r = mmenu.checkMenuFile(file)

	if 'error' in r:
		return make_response(r['error'], 500)
	else:
		return jsonify(r)

@api.route("/maintenance-menu", methods=["DELETE"])
@restricted_access
def deleteMaintenanceMenu():
	data = request.json
	tId = data.get('id', None)

	if tId:
		mmenu = maintenanceMenuManager()
		r = mmenu.removeMenu(tId)

		if 'error' in r:
			error = r['error']

			if error == 'not_found':
				return make_response('Not Found', 404)
			else:
				return make_response(error, 500)

		else:
			return jsonify(r)

	return make_response('Invalid Request', 400)

@api.route("/maintenance-menu/install", methods=["POST"])
@restricted_access
def installMaintenanceMenu():
	data = request.json
	file = data.get('file', None)
	if file:
		mmenu = maintenanceMenuManager()
		if mmenu.installFile(file):
			return jsonify()
		else:
			return make_response('Unable to Install', 500)

	return make_response('Invalid Request', 400)
