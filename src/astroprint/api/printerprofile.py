# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import request, jsonify

from octoprint.server.api import api
from octoprint.server import restricted_access

from astroprint.printerprofile import printerProfileManager
from astroprint.plugin import pluginManager

@api.route('/printer-profile', methods=['PATCH', 'GET'])
@restricted_access
def printer_profile_patch():
	ppm = printerProfileManager()

	if request.method == "PATCH":
		changes = request.json

		if 'cancel_gcode' in changes:
			changes['cancel_gcode'] = changes['cancel_gcode'].strip().split('\n');

		ppm.set(changes)
		ppm.save()

		return jsonify()

	else:

		plugins = pluginManager().getPluginsByService('printerComms')

		result = {
			'profile': ppm.data,
			'choices': {
				("plugin:%s" % k) : { 'name': plugins[k].definition['name'], 'properties': plugins[k].properties }
			for k in plugins }
		}

		result['choices'].update({
			'marlin': {'name': 'GCODE - Marlin / Repetier Firmware', 'properties': {'customCancelCommands': True}},
			's3g': {'name': 'X3G - Sailfish / Makerbot Firmware',  'properties': {'customCancelCommands': False}}
		})

		return jsonify( result )
