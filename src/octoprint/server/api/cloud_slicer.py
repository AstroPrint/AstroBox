# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import json
import uuid

from flask import request, jsonify, abort

from octoprint.settings import settings
from octoprint.server import restricted_access, printer, SUCCESS, gcodeManager
from octoprint.server.api import api
from octoprint.events import eventManager, Events
from octoprint.filemanager.destinations import FileDestinations

from octoprint.slicers.cloud.proven_to_print import ProvenToPrintSlicer

#~~ Cloud Slicer control

@api.route('/cloud-slicer', methods=['DELETE'])
@restricted_access
def cloud_slicer_logout():
	s = settings()
	s.set(["cloudSlicer", "privateKey"], None)
	s.set(["cloudSlicer", "publicKey"], None)
	s.set(["cloudSlicer", "email"], None)
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

@api.route("/cloud-slicer/print-files", methods=["GET"])
@restricted_access
def designs():
	slicer = ProvenToPrintSlicer()
	cloud_files = json.loads(slicer.print_files())

	local_files = list(gcodeManager.getAllFileData())

	for p in cloud_files:
		p['local_filename'] = None
		for i in range(len(local_files)):
			if "cloud_id" in local_files[i] and p['id'] == local_files[i]['cloud_id']:
				local_file = local_files[i]
				p['local_filename'] = local_file['name']
				p['local_only'] = False
				del local_files[i]
				break

	if local_files:
		for p in local_files:
			p['id'] = uuid.uuid4().hex
			p['local_filename'] = p['name']
			p['local_only'] = True
			p['info'] = p['gcodeAnalysis']
			del p['gcodeAnalysis']

	return json.dumps(local_files + cloud_files)

@api.route("/cloud-slicer/print-files/<string:print_file_id>/download", methods=["GET"])
@restricted_access
def design_download(print_file_id):
	if not bool(settings().get(["cloudSlicer", "publicKey"])):
		abort(401)

	slicer = ProvenToPrintSlicer()
	em = eventManager()

	def progressCb(progress):
		em.fire(
			Events.CLOUD_DOWNLOAD, {
				"type": "progress",
				"id": print_file_id,
				"progress": progress
			}
		)

	def successCb(destFile, fileInfo):
		if gcodeManager.saveCloudGcode(destFile, fileInfo, FileDestinations.LOCAL):
			em.fire(
				Events.CLOUD_DOWNLOAD, {
					"type": "success",
					"id": print_file_id,
					"filename": gcodeManager._getBasicFilename(destFile),
					"info": fileInfo["info"]
				}
			)

		else:
			errorCb(destFile, "Couldn't save the file")

	def errorCb(destFile, error):
		em.fire(
			Events.CLOUD_DOWNLOAD, 
			{
				"type": "error",
				"id": print_file_id,
				"reason": error
			}
		)
		
		if os.path.exists(destFile):
			os.remove(destFile)

	if slicer.download_print_file(print_file_id, progressCb, successCb, errorCb):
		return jsonify(SUCCESS)
			
	return abort(400)