# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import octoprint.util as util
from flask import jsonify, request, abort
from octoprint.server import restricted_access, SUCCESS
from octoprint.server.api import api

from astroprint.camera import cameraManager
from astroprint.boxrouter.handlers.requesthandler import P2PCommandHandler 


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
	
@api.route("/camera/startStreaming", methods=["POST"])
@restricted_access
def start_streaming():
	print 'startStreaming'
	print request
	response = P2PCommandHandler().init_connection(None,None)

	print response
	return jsonify(response)


@api.route("/camera/stopStreaming", methods=["POST"])
@restricted_access
def stop_streaming():
	print 'stopStreaming'
	data = request.json
	
	P2PCommandHandler().stop_connection(data,None)
	
	return jsonify(SUCCESS)
