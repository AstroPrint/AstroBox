# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import octoprint.util as util
from flask import jsonify, request, abort, make_response
from octoprint.server import restricted_access, SUCCESS
from octoprint.server.api import api
from octoprint.settings import settings

from astroprint.camera import cameraManager
from astroprint.webrtc import webRtcManager

@api.route("/camera/is-camera-supported", methods=["GET"])
@restricted_access
def isCameraSupportedByAstrobox():
	cm = cameraManager()

	return jsonify({"isCameraSupported": cm.settingsStructure() is not None})

@api.route("/camera/refresh-plugged", methods=["POST"])
@restricted_access
def refreshPluggedCamera():
	cm = cameraManager()

	return jsonify({"isCameraPlugged": cm.reScan()})

@api.route("/camera/has-properties", methods=["GET"])
@restricted_access
def hasCameraProperties():
	cm = cameraManager()

	return jsonify({"hasCameraProperties": cm.hasCameraProperties()})

@api.route("/camera/is-resolution-supported", methods=["GET"])
@restricted_access
def isResolutionSupported():
	cm = cameraManager()
	size = request.values['size']

	return jsonify({"isResolutionSupported": cm.isResolutionSupported(size)})


@api.route("/camera/connected", methods=["GET"])
@restricted_access
def isCameraConnected():
	cm = cameraManager()

	return jsonify({"isCameraConnected": cm.isCameraConnected(), "cameraName": cm.cameraName})


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
			timelapse = cm.start_timelapse(freq)
			if timelapse == 'success':
				return jsonify(SUCCESS)
			if timelapse == 'no_storage':
				return make_response('No Storage', 402)
			else:
				abort (500)

	else:
		abort(400)

	abort(500)

@api.route("/camera/init-janus", methods=["POST"])
@restricted_access
def init_janus():
	#Start session in Janus
	if webRtcManager().startJanus():
		return jsonify(SUCCESS)

	abort(500)

@api.route("/camera/peer-session", methods=["POST", "DELETE"])
@restricted_access
def peer_session():
	data = request.json
	if data and 'sessionId' in data:
		sessionId = data['sessionId']

		if request.method == 'POST':
			#Initialize the peer session
			if cameraManager().startLocalVideoSession(sessionId):
				return jsonify(SUCCESS)

			abort(500)

		elif request.method == 'DELETE':
			#Close peer session
			if cameraManager().closeLocalVideoSession(sessionId):
				return jsonify(SUCCESS)

			else:
				abort(500)

	else:
		abort(400)

@api.route("/camera/start-streaming",methods=["POST"])
@restricted_access
def start_streaming():
	webRtcManager().startVideoStream()

	return jsonify(SUCCESS)
