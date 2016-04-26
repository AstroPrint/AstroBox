# coding=utf-8	
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import octoprint.util as util
from flask import jsonify, request, abort
from octoprint.server import restricted_access, SUCCESS
from octoprint.server.api import api

from astroprint.camera import cameraManager
from astroprint.webrtc import webRtcManager

@api.route("/camera/is-resolution-supported", methods=["POST"])
@restricted_access
def isResolutionSupported():

	cm = cameraManager()
	size = request.values['size']

	return jsonify({"isResolutionSupported": cm.isResolutionSupported(size)})


@api.route("/camera/is-camera-available", methods=["POST"])
@restricted_access
def isCameraAvailable():

	cm = cameraManager()

	return jsonify({"isCameraAvailable": cm.isCameraAvailable()})


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
	if webRtcManager().ensureJanusRunning():
		return jsonify(SUCCESS)

	abort(500)


@api.route("/camera/start-peer-session", methods=["POST"])
@restricted_access
def start_peer_session():
	#Initialize the peer session
	sessionId = webRtcManager().startLocalSession()
	return jsonify({"sessionId": sessionId})


@api.route("/camera/close-peer-session", methods=["POST"])
@restricted_access
def close_peer_session():
	#Close peer session
	data = request.json
	webRtcManager().closeLocalSession(data['sessionId'])
	return jsonify(SUCCESS)


@api.route("/camera/start-streaming",methods=["POST"])
@restricted_access
def start_streaming():
	#open_camera
	webRtcManager().startGStreamer()
	
	return jsonify(SUCCESS) 
