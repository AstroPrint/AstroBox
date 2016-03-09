# coding=utf-8	
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import octoprint.util as util
from flask import jsonify, request, abort
from octoprint.server import restricted_access, SUCCESS
from octoprint.server.api import api

from astroprint.camera import cameraManager
from astroprint.webrtc import LocalConnectionPeer, webRtcManager

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
	sessionId = LocalConnectionPeer().startJanusSec()

	if sessionId:
		return jsonify(sesionId= sessionId)

	abort(500)

@api.route("/camera/stop-janus", methods=["POST"])
@restricted_access
def stop_janus():
	#Stop session in Janus
	LocalConnectionPeer().stopJanusSec()
	return jsonify(SUCCESS)

@api.route("/camera/start-peer-session", methods=["POST"])
@restricted_access
def start_peer_session():
	#Initialize the peer session
	data = request.json
	sessionId = LocalConnectionPeer().startPeerSession(data['clientId'])
	return jsonify({"sessionId": sessionId})

@api.route("/camera/close-peer-session", methods=["POST"])
@restricted_access
def close_peer_session():
	#Close peer session
	data = request.json
	print data
	LocalConnectionPeer().closePeerSession(data['sessionId'])
	return jsonify(SUCCESS)
