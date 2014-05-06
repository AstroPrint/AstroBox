# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os

from flask import request, jsonify, abort

from octoprint.settings import settings
from octoprint.server import restricted_access, printer, SUCCESS, gcodeManager
from octoprint.server.api import api
from octoprint.events import eventManager
from octoprint.filemanager.destinations import FileDestinations

from octoprint.slicers.cloud.proven_to_print import ProvenToPrintSlicer

#~~ Cloud Slicer control

@api.route('/cloud-slicer/upload-data', methods=['GET'])
@restricted_access
def upload_data():
	filePath = request.args.get('file', None)

	if filePath:
		slicer = ProvenToPrintSlicer()

		url, params, redirect_url = slicer.get_upload_info(filePath)
		return jsonify(url=url, params=params, redirect=redirect_url)

	abort(400)

@api.route("/cloud-slicer/command", methods=["POST"])
@restricted_access
def command():
	if not bool(settings().get(["cloudSlicer", "publicKey"])):
		abort(401)

	if "command" in request.values.keys():
		slicer = ProvenToPrintSlicer()

		command = request.values["command"]
		if command == "refresh":
			return slicer.refresh_files()

		elif command == "download":
			gcode_id = request.values['gcode_id']
			filename = request.values['filename']

			if gcode_id and filename:
				filename = (filename[:-4] if filename[-4:] in ['.stl', '.obj' , '.amf'] else filename) + ".gcode"
				destFile = gcodeManager.getAbsolutePath(filename, mustExist=False)

				def progressCb(progress):
					eventManager().fire(
						"CloudDownloadEvent", {
							"type": "progress",
							"id": gcode_id,
							"progress": progress
						}
					)

				def successCb():
					class Callback():
						def sendUpdateTrigger(self, type):
							gcodeManager.unregisterCallback(self)

							eventManager().fire(
								"CloudDownloadEvent", {
									"type": "success",
									"id": gcode_id,
									"filename": filename
								}
							)

					gcodeManager.registerCallback(Callback());
					if gcodeManager.processGcode(destFile, FileDestinations.LOCAL):
						eventManager().fire(
							"CloudDownloadEvent", {
								"type": "analyzing",
								"id": gcode_id
							}
						)
					else:
						errorCb("Couldn't save the file")

				def errorCb(error):
					eventManager().fire(
						"CloudDownloadEvent", 
						{
							"type": "error",
							"id": gcode_id,
							"filename": filename, 
							"reason": error
						}
					)
					
					if os.path.exists(destFile):
						os.remove(destFile)

				if slicer.download_gcode_file(gcode_id, destFile, progressCb, successCb, errorCb):
					return jsonify(SUCCESS)
			
	return abort(400)