# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import request, jsonify

from octoprint.server.api import api
from octoprint.server import restricted_access

from astroprint.printerprofile import printerProfileManager
import uuid


@api.route('/printer-profile', methods=['PATCH', 'GET'])
@restricted_access
def printer_profile_patch():
	ppm = printerProfileManager()

	if request.method == "PATCH":
		changes = request.json

		ppm.set(changes)
		ppm.save()

		return jsonify()

	else:

		result = ppm.data.copy()
		result.update( {"driverChoices": ppm.driverChoices()} )

		return jsonify( result )

@api.route('/temperature-preset', methods=['POST'])
@restricted_access
def temp_preset_post():

	id = uuid.uuid4().hex
	name = request.values.get('name', None)
	nozzle_temp = request.values.get('nozzle_temp', None)
	bed_temp = request.values.get('bed_temp', None)

	temp_update = { 'id' : id, 'name' : name, 'nozzle_temp' : nozzle_temp, 'bed_temp' : bed_temp}

	ppm = printerProfileManager()
	changes = ppm.data.copy()
	changes['temp_presets'].append(temp_update)

	ppm.set(changes)
	ppm.save()

	return jsonify( {'id' : id} )
