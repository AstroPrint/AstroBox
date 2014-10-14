# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
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
		if cm.activeTimelapse:
			if cm.update_timelapse(freq):
				if not cm.activeTimelapse.isAlive():
					cm.resume_timelapse()

				return jsonify(SUCCESS)
				
		else:
			if cm.start_timelapse(freq):
				return jsonify(SUCCESS)

	else:
		abort(400)

	abort(500)


@api.route("/camera/timelapse", methods=["DELETE"])
def pause_timelapse():
	cm = cameraManager()
	if cm.activeTimelapse and cm.activeTimelapse.isAlive():
		cm.pause_timelapse()
		return jsonify(SUCCESS)
			
	else:
		abort(404)