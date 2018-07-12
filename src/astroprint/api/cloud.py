# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import json
import uuid

from flask import request, jsonify, abort
from flask_login import current_user
from requests import ConnectionError

from octoprint.settings import settings
from octoprint.server import restricted_access, SUCCESS
from octoprint.server.api import api
from octoprint.events import eventManager, Events

from astroprint.cloud import astroprintCloud, AstroPrintCloudNoConnectionException
from astroprint.printfiles.downloadmanager import downloadManager
from astroprint.printer.manager import printerManager

#~~ Cloud Slicer control

@api.route('/astroprint', methods=['DELETE'])
@restricted_access
def cloud_slicer_logout():
	astroprintCloud().signout()
	return jsonify(SUCCESS)

@api.route('/astroprint/private-key', methods=['POST'])
def set_private_key():
	email = request.values.get('email', None)
	password = request.values.get('password', None)
	private_key = request.values.get('private_key', None)

	if email and password:
		try:
			if astroprintCloud().signin(email, password):
				return jsonify(SUCCESS)

		except (AstroPrintCloudNoConnectionException, ConnectionError):
			abort(503, "AstroPrint.com can't be reached")

	elif email and private_key:
		try:
			if astroprintCloud().signinWithKey(email, private_key):
				return jsonify(SUCCESS)

		except (AstroPrintCloudNoConnectionException, ConnectionError):
			abort(503, "AstroPrint.com can't be reached")

	else:
		abort(400)

	abort(401)

@api.route('/astroprint/login-key', methods=['GET'])
@restricted_access
def get_login_key():
	try:
		key = astroprintCloud().get_login_key()
		if key:
			return jsonify(key)

	except (AstroPrintCloudNoConnectionException, ConnectionError):
		abort(503, "AstroPrint.com can't be reached")

	abort(401)

@api.route('/astroprint/upload-data', methods=['GET'])
@restricted_access
def upload_data():
	filePath = request.args.get('file', None)

	if filePath:
		uploadInfo = astroprintCloud().get_upload_info(filePath)

		if uploadInfo:
			if 'error' in uploadInfo:
				if uploadInfo['error'] == 'no_user':
					abort(401)
				else:
					abort(500)

			else:
				return json.dumps(uploadInfo)
		else:
			abort(500)

	abort(400)

@api.route("/astroprint/print-files", methods=["GET"])
@restricted_access
def designs():
	forceSyncCloud = request.args.get('forceSyncCloud')
	cloud_files = json.loads(astroprintCloud().print_files(forceSyncCloud))
	local_files = list(printerManager().fileManager.getAllFileData())

	if cloud_files:
		for p in cloud_files:
			p['local_filename'] = None
			p['last_print'] = None
			p['uploaded_on'] = None
			for i in range(len(local_files)):
				cloud_id = local_files[i].get("cloud_id")
				if cloud_id and p['id'] == cloud_id:
					local_file = local_files[i]
					p['local_filename'] = local_file['name']
					p['local_only'] = False
					p['uploaded_on'] = local_file['date']
					gcodeAnalysis = local_file.get("gcodeAnalysis")
					if gcodeAnalysis:
						p["info"] = gcodeAnalysis

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
			p['uploaded_on'] = p['date']
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
	if current_user is None or not current_user.is_authenticated or not current_user.publicKey:
		abort(401)

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
		if fileInfo is True:
			#This means the files was already on the device
			em.fire(
				Events.CLOUD_DOWNLOAD, {
					"type": "success",
					"id": print_file_id
				}
			)

	def errorCb(destFile, error):
		if error == 'cancelled':
			em.fire(
					Events.CLOUD_DOWNLOAD,
					{
						"type": "cancelled",
						"id": print_file_id
					}
				)
		else:
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

	if astroprintCloud().download_print_file(print_file_id, progressCb, successCb, errorCb):
		return jsonify(SUCCESS)

	return abort(400)

@api.route("/astroprint/print-files/<string:print_file_id>/download", methods=["DELETE"])
@restricted_access
def cancel_design_download(print_file_id):
	if downloadManager().cancelDownload(print_file_id):
		return jsonify(SUCCESS)

	else:
		return abort(404)

@api.route("/astroprint/print-jobs/<string:print_job_id>/add-reason", methods=["PUT"])
@restricted_access
def update_cancel_reason(print_job_id):
	if not "application/json" in request.headers["Content-Type"]:
		return abort(400)

	data = request.json

	#get reason
	reason = {}
	if 'reason' in data:
		reason['reason_id'] = data['reason']

	if 'other_text' in data:
		reason['other_text'] = data['other_text']

	if reason:
		if not astroprintCloud().updateCancelReason(print_job_id, reason):
			return abort(500)
		else:
			return jsonify(SUCCESS)
	else:
		return abort(400)





