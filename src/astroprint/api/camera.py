# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import octoprint.util as util
from flask import jsonify, request, abort
from octoprint.server import restricted_access, SUCCESS
from octoprint.server.api import api

from astroprint.camera import cameraManager
from astroprint.webrtc import webRtcManager

@api.route("/camera/timelapse", methods=["POST"])
@restricted_access
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
	
@api.route("/camera/init-janus", methods=["POST"])
@restricted_access
def init_janus():
	#Start session in Janus
	sessionId = webRtcManager().startPeerSession(None)

	if sessionId:
		return jsonify(sesionId= sessionId)

	abort(500)

@api.route("/camera/stop-janus", methods=["POST"])
@restricted_access
def stop_janus():
	#Stop session in Janus
	data = request.json
	webRtcManager().closePeerSession(data['sessionId'])
	return jsonify(SUCCESS)
