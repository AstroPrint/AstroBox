# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import json
import uuid

from flask import request, jsonify, abort

from octoprint.settings import settings
from octoprint.server import restricted_access, SUCCESS, gcodeManager
from octoprint.server.api import api
from octoprint.events import eventManager, Events
from octoprint.filemanager.destinations import FileDestinations
from astroprint.cloud import astroprintCloud

#~~ Cloud Slicer control

@api.route('/astroprint', methods=['DELETE'])
@restricted_access
def cloud_slicer_logout():
	ap = astroprintCloud()
	ap.signout()
	return jsonify(SUCCESS)	

@api.route('/astroprint/private-key', methods=['POST'])
def set_private_key():
	email = request.values.get('email', None)
	password = request.values.get('password', None)

	if email and password:
		ap = astroprintCloud()
		if ap.signin(email, password):
			return jsonify(SUCCESS)	

	else:
		abort(400)

	abort(401)

@api.route('/astroprint/upload-data', methods=['GET'])
@restricted_access
def upload_data():
	filePath = request.args.get('file', None)

	if filePath:
		slicer = astroprintCloud()

		url, params, redirect_url = slicer.get_upload_info(filePath)
		return jsonify(url=url, params=params, redirect=redirect_url)

	abort(400)

@api.route("/astroprint/print-files", methods=["GET"])
@restricted_access
def designs():
	slicer = astroprintCloud()
	forceSyncCloud = request.args.get('forceSyncCloud')
	cloud_files = json.loads(slicer.print_files(forceSyncCloud))
	local_files = list(gcodeManager.getAllFileData())

	if cloud_files:
		for p in cloud_files:
			p['local_filename'] = None
			p['last_print'] = None
			for i in range(len(local_files)):
				if "cloud_id" in local_files[i] and p['id'] == local_files[i]['cloud_id']:
					local_file = local_files[i]
					p['local_filename'] = local_file['name']
					p['local_only'] = False
					
					if 'prints' in local_file \
						and 'last' in local_file['prints'] \
						and local_file['prints']['last'] \
						and 'date' in local_file['prints']['last']:
						p['last_print'] = local_file['prints']['last']['date']

					del local_files[i]

					break

		cloud_files = sorted(cloud_files, key=lambda e: e['local_filename'] is None)

	else:
		cloud_files = []

	if local_files:
		for p in local_files:
			p['id'] = uuid.uuid4().hex
			p['local_filename'] = p['name']
			p['local_only'] = True
			p['last_print'] = None
			if 'gcodeAnalysis' in p:
				p['info'] = p['gcodeAnalysis']
				del p['gcodeAnalysis']
			else:
				p['info'] = None

			if 'prints' in p \
				and 'last' in p['prints'] \
				and p['prints']['last'] \
				and 'date' in p['prints']['last']:
				p['last_print'] = p['prints']['last']['date']
				del p['prints']

	else:
		local_files = []

	files = sorted(local_files + cloud_files, key=lambda e: e['last_print'], reverse=True)

	return json.dumps(files)

@api.route("/astroprint/print-files/<string:print_file_id>/download", methods=["GET"])
@restricted_access
def design_download(print_file_id):
	if not bool(settings().get(["cloudSlicer", "publicKey"])):
		abort(401)

	slicer = astroprintCloud()
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
		
		if destFile and os.path.exists(destFile):
			os.remove(destFile)

	if slicer.download_print_file(print_file_id, progressCb, successCb, errorCb):
		return jsonify(SUCCESS)
			
	return abort(400)