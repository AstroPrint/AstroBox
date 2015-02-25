# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import request, jsonify

from octoprint.server.api import api
from octoprint.server import restricted_access

from astroprint.printerprofile import printerProfileManager

@api.route('/printer-profile', methods=['PATCH'])
@restricted_access
def printer_profile_patch():
	changes = request.json

	ppm = printerProfileManager()
	ppm.set(changes)
	ppm.save()

	return jsonify()