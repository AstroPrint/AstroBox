# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import json

from flask import request, jsonify, abort

from octoprint.settings import settings
from octoprint.server import restricted_access, printer, SUCCESS, gcodeManager
from octoprint.server.api import api
from octoprint.events import eventManager
from octoprint.filemanager.destinations import FileDestinations

from octoprint.slicers.cloud.proven_to_print import ProvenToPrintSlicer

#~~ Cloud Slicer control

@api.route('/cloud-slicer', methods=['DELETE'])
@restricted_access
def cloud_slicer_logout():
	s = settings()
	s.set(["cloudSlicer", "privateKey"], '')
	s.set(["cloudSlicer", "publicKey"], '')
	s.set(["cloudSlicer", "email"], '')
	s.save()
	return jsonify(SUCCESS)	

@api.route('/cloud-slicer/private-key', methods=['POST'])
def get_private_key():
	email = request.values.get('email', None)
	password = request.values.get('password', None)

	if email and password:
		slicer = ProvenToPrintSlicer()

		private_key = slicer.get_private_key(email, password)

		if private_key:
			public_key = slicer.get_public_key(email, private_key)

			if public_key:
				s = settings()
				s.set(["cloudSlicer", "privateKey"], private_key)
				s.set(["cloudSlicer", "publicKey"], public_key)
				s.set(["cloudSlicer", "email"], email)
				s.save()
				return jsonify(SUCCESS)

	else:
		abort(400)

	abort(401)

@api.route('/cloud-slicer/upload-data', methods=['GET'])
@restricted_access
def upload_data():
	filePath = request.args.get('file', None)

	if filePath:
		slicer = ProvenToPrintSlicer()

		url, params, redirect_url = slicer.get_upload_info(filePath)
		return jsonify(url=url, params=params, redirect=redirect_url)

	abort(400)

@api.route("/cloud-slicer/designs", methods=["GET"])
@restricted_access
def designs():
	if not bool(settings().get(["cloudSlicer", "publicKey"])):
		abort(401)

	slicer = ProvenToPrintSlicer()
	cloud_designs = json.loads(slicer.design_files())

	local_files = list(gcodeManager.getAllFileData())

	for d in cloud_designs:
		for p in d['gcodes']:
			p['local_filename'] = None
			for i in range(len(local_files)):
				if "cloud_id" in local_files[i] and p['id'] == local_files[i]['cloud_id']:
					p['local_filename'] = local_files[i]['name']
					del local_files[i]
					break

	return json.dumps(cloud_designs)

@api.route("/cloud-slicer/designs/download/<string:id>", methods=["GET"])
@restricted_access
def design_download(id):
	if not bool(settings().get(["cloudSlicer", "publicKey"])):
		abort(401)

	slicer = ProvenToPrintSlicer()
	em = eventManager()

	def progressCb(progress):
		em.fire(
			"CloudDownloadEvent", {
				"type": "progress",
				"id": id,
				"progress": progress
			}
		)

	def successCb(destFile):
		class Callback():
			def sendEvent(self, type):
				gcodeManager.unregisterCallback(self)

				em.fire(
					"CloudDownloadEvent", {
						"type": "success",
						"id": id
					}
				)

		gcodeManager.registerCallback(Callback());
		if gcodeManager.processGcode(destFile, FileDestinations.LOCAL):
			metadata = gcodeManager.getFileMetadata(destFile)
			metadata["cloud_id"] = id
			gcodeManager.setFileMetadata(destFile, metadata)

			em.fire(
				"CloudDownloadEvent", {
					"type": "analyzing",
					"id": id,
					"filename": gcodeManager._getBasicFilename(destFile)
				}
			)
		else:
			errorCb(destFile, "Couldn't save the file")

	def errorCb(destFile, error):
		em.fire(
			"CloudDownloadEvent", 
			{
				"type": "error",
				"id": id,
				"reason": error
			}
		)
		
		if os.path.exists(destFile):
			os.remove(destFile)

	if slicer.download_gcode_file(id, progressCb, successCb, errorCb):
		return jsonify(SUCCESS)
			
	return abort(400)