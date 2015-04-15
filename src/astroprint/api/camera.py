# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from flask import jsonify, request, abort

from octoprint.server import SUCCESS
from octoprint.server.api import api
from astroprint.camera import cameraManager

@api.route("/camera/timelapse", methods=["POST"])
def update_timelapse():
	freq = request.values.get('freq')

	if freq:
		cm = cameraManager()
		if cm.timelapseInfo:
			if cm.update_timelapse(freq):
				return jsonify(SUCCESS)
				
		else:
			if cm.start_timelapse(freq):
				return jsonify(SUCCESS)

	else:
		abort(400)

	abort(500)
