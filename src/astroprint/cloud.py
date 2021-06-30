__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2016-2020 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def astroprintCloud():
	global _instance
	if _instance is None:
		_instance = AstroPrintCloud()
	return _instance

import requests
import hmac
import binascii
import uuid
import os
import json
import logging

from urllib import quote_plus
from os.path import splitext, split
from hashlib import sha256

from time import sleep

from requests_toolbelt import MultipartEncoder
from requests import ConnectionError

from flask import current_app
from flask_login import login_user, logout_user, current_user
from flask_principal import Identity, identity_changed, AnonymousIdentity

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from astroprint.software import softwareManager
from astroprint.boxrouter import boxrouterManager
from astroprint.printer.manager import printerManager
from astroprint.printfiles.downloadmanager import downloadManager
from astroprint.ro_config import roConfig
from astroprint.network.manager import networkManager

class AstroPrintCloudException(Exception):
	pass

class AstroPrintCloudInsufficientPermissionsException(AstroPrintCloudException):
	def __init__(self, data):
		self.data = data

class AstroPrintCloudNoConnectionException(AstroPrintCloudException):
	#There no connection to the astroprint cloud
	pass

class AstroPrintCloudTemporaryErrorException(AstroPrintCloudException):
	#Temporary connection or server issue
	def __init__(self, code):
		self.code = code

class HMACAuth(requests.auth.AuthBase):
	def __init__(self, publicKey, privateKey, boxId, orgId = None,  groupId = None,):
		self.publicKey = publicKey
		self.privateKey = privateKey
		self.groupId = groupId
		self.orgId = orgId
		self.boxId = boxId
		self.isOnFleet = self.groupId and self.orgId

	def updateFleetInfo(self, orgId = None,  groupId = None):
		self.groupId = groupId
		self.orgId = orgId
		self.isOnFleet = self.groupId and self.orgId

	def __call__(self, r):

		r.headers['User-Agent'] = softwareManager().userAgent
		sig_base = '&'.join((r.method, r.headers['User-Agent']))

		hashed = hmac.new(self.privateKey, sig_base, sha256)

		r.headers['X-Public'] = self.publicKey
		r.headers['X-Hash'] = binascii.b2a_base64(hashed.digest())[:-1]
		r.headers['X-Box-Id'] = self.boxId
		if self.isOnFleet:
			r.headers['X-Org-Id'] = self.orgId
			r.headers['X-Group-Id'] = self.groupId

		return r

class AstroPrintCloud(object):
	def __init__(self):
		self.settings = settings()
		self._eventManager = eventManager()
		self.hmacAuth = None
		self.boxId = boxrouterManager().boxId

		self.tryingLoggingTimes = 0

		self.apiHost = roConfig('cloud.apiHost')
		self._print_file_store = None
		self._sm = softwareManager()
		self._logger = logging.getLogger(__name__)

		loggedUser = self.settings.get(['cloudSlicer', 'loggedUser'])
		if loggedUser:
			from octoprint.server import userManager

			user = userManager.findUser(loggedUser)

			if user and user.publicKey and user.privateKey:
				self.hmacAuth = HMACAuth(user.publicKey, user.privateKey, self.boxId, user.orgId, user.groupId)

	def updateFleetInfo(self, orgId, groupId):
		loggedUser = self.settings.get(['cloudSlicer', 'loggedUser'])
		if loggedUser:
			from octoprint.server import userManager
			user = userManager.findUser(loggedUser)
			if(user and user.groupId != groupId):
				self._logger.info("Box is part of fleet [%s] in group [%s]" % (orgId, groupId))
				userManager.changeUserFleetInfo(loggedUser, orgId, groupId)
				self.hmacAuth.updateFleetInfo(orgId, groupId)

	def validateUnblockCode(self, code):
		if self.fleetId:
			try:
				r = requests.post( "%s/astrobox/%s/check-unblock-code" % (self.apiHost, self.boxId), data= {'code': code}, auth=self.hmacAuth )
				if r.status_code == 200:
					self.remove_logged_user()
					return True
				else:
					self._logger.error('Unblock request failed with: %s' % r.status_code)

			except Exception as e:
				self._logger.exception(e)

		return False

	def cloud_enabled(self):
		return roConfig('cloud.apiHost') and self.hmacAuth

	@property
	def fleetId(self):
		if self.hmacAuth:
			return self.hmacAuth.orgId
		return None

	@property
	def groupId(self):
		if self.hmacAuth:
			return self.hmacAuth.groupId
		return None

	@property
	def orgId(self):
		if self.hmacAuth:
			return self.hmacAuth.orgId
		return None

	def signin(self, email, password, hasSessionContext = True):
		from octoprint.server import userManager
		user = None
		userLoggedIn = False
		online = networkManager().isOnline()

		if online:
			data_private_key = self.get_private_key(email, password)

			if data_private_key:
				private_key = data_private_key['private_key']
				public_key = self.get_public_key(email, private_key)
				orgId = data_private_key['organization_id']
				groupId = data_private_key['group_id']

				if public_key:
					#Let's protect the box now:

					#We need to keep this code for a while, or it can generate errors it the user who is loging whast loged before
					user = userManager.findUser(email)
					if user:
						userManager.changeUserPassword(email, password)
						userManager.changeCloudAccessKeys(email, public_key, private_key, orgId, groupId)
					else:
						user = userManager.addUser(email, password, public_key, private_key, orgId, groupId, True)

					userLoggedIn = True

		else:
			user = userManager.findUser(email)
			userLoggedIn = user and user.check_password(userManager.createPasswordHash(password))

		if userLoggedIn:
			if hasSessionContext:
				login_user(user, remember=True)

			userId = user.get_id()

			self.settings.set(["cloudSlicer", "loggedUser"], userId)
			self.settings.save()

			boxrouterManager().boxrouter_connect()

			if hasSessionContext:
				identity_changed.send(current_app._get_current_object(), identity=Identity(userId))

			#let the singleton be recreated again, so new credentials are taken into use
			global _instance
			_instance = None

			eventManager().fire(Events.LOCK_STATUS_CHANGED, userId)

			return True

		elif not online:
			raise AstroPrintCloudNoConnectionException()

		return False

	def validatePassword(self, email, password):
		from octoprint.server import userManager
		user = None
		userValidated = False

		online = networkManager().isOnline()

		if online:
			try:
				data_private_key = self.get_private_key(email, password)

				if data_private_key:
					private_key = data_private_key['private_key']
					public_key = self.get_public_key(email, private_key)
					orgId = data_private_key['organization_id']
					groupId = data_private_key['group_id']

					if public_key:
						#Let's update the box now:
						user = userManager.findUser(email)
						if user:
							userManager.changeUserPassword(email, password)
							userManager.changeCloudAccessKeys(email, public_key, private_key, orgId, groupId)
						else:
							user = userManager.addUser(email, password, public_key, private_key, orgId, groupId, True)

						userValidated = True

					else:
						return False

				else:
					return False

			except ConnectionError as e:
				self._logger.error('Connection error when trying to validate password: %s' % e)
				raise AstroPrintCloudNoConnectionException()

		# was offline or couldn't reach astroprint.com
		if not userValidated:
			user = userManager.findUser(email)
			userValidated = user and user.check_password(userManager.createPasswordHash(password))

		if userValidated:
			userId = user.get_id()
			self.settings.set(["cloudSlicer", "loggedUser"], userId)
			self.settings.save()

		return userValidated

	def signinWithKey(self, email, private_key, hasSessionContext = True):
		from octoprint.server import userManager

		user = None
		userLoggedIn = False

		online = networkManager().isOnline()

		if online:
			public_key = self.get_public_key(email, private_key)

			if public_key:
				#Let's protect the box now:
				user = userManager.findUser(email)

				if user and user.has_password():
					userManager.changeCloudAccessKeys(email, public_key, private_key)
				else:
					self._logger.info("New user signing requires password method")
					return False

				userLoggedIn = True

		else:
			user = userManager.findUser(email)
			userLoggedIn = user and user.check_privateKey(private_key)

		if userLoggedIn:
			if hasSessionContext:
				login_user(user, remember=True)

			userId = user.get_id()

			self.settings.set(["cloudSlicer", "loggedUser"], userId)
			self.settings.save()

			boxrouterManager().boxrouter_connect()

			if hasSessionContext:
				identity_changed.send(current_app._get_current_object(), identity=Identity(userId))

			#let the singleton be recreated again, so new credentials are taken into use
			global _instance
			_instance = None

			eventManager().fire(Events.LOCK_STATUS_CHANGED, userId)
			return True

		elif not online:
			raise AstroPrintCloudNoConnectionException()

		return False

	def remove_logged_user(self):
		loggedUser = self.settings.get(['cloudSlicer', 'loggedUser'])
		from octoprint.server import userManager
		#Method could be call twice (boxrouter, touch), and now user is deleted
		if loggedUser:
			userManager.removeUser(loggedUser)
		self.settings.set(["cloudSlicer", "loggedUser"], None)
		self.settings.set(["materialSelected"], None)
		self.settings.set(["printerSelected"], None)
		self.settings.set(["qualitySelected"], None)
		self.settings.set(["customQualitySelected"], None)
		self.settings.save()
		boxrouterManager().boxrouter_disconnect()

		#let the singleton be recreated again, so credentials and print_files are forgotten
		global _instance
		_instance = None

		eventManager().fire(Events.LOCK_STATUS_CHANGED, None)

	def signout(self, hasSessionContext = True):
		if hasSessionContext:
			from flask import session

			logout_user()

			for key in ('identity.name', 'identity.auth_type'):
				session.pop(key, None)

			identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())

		self.remove_logged_user()

	def get_local_certificate(self):
		try:
			#Get credentials to upload the file
			r = requests.get( "%s/ssl/new-cert" % self.apiHost, auth=self.hmacAuth )
			return r.text

		except Exception as e:
			self._logger.error('', exc_info=True)
			return None

	def get_upload_info(self, filePath):
		_, filename = split(filePath)
		_, fileExtension = splitext(filename)
		design_id = uuid.uuid4().hex
		s3_key = design_id + fileExtension

		#only registered users can upload files to the cloud
		if current_user and not current_user.is_anonymous:
			try:
				#Get credentials to upload the file
				r = requests.get( "%s/designs/upload/params?key=%s" % (self.apiHost, s3_key), auth=self.hmacAuth )
				data = r.json()
			except:
				data = None

			if data and 'url' in data and 'post_data' in data:
				publicKey = current_user.publicKey
				privateKey = current_user.privateKey

				request = json.dumps({
					'design_id': design_id,
					's3_key': s3_key,
					'filename': filename
				})

				hashed = hmac.new(privateKey, request, sha256)
				signature = binascii.b2a_base64(hashed.digest())[:-1]

				redirect_url = "%s/design/uploaded?public_key=%s&req=%s&sig=%s" % (
					self.apiHost.replace('api', 'cloud'),
					publicKey,
					quote_plus(request),
					quote_plus(signature))

				#url, post parameters, redirect Url
				return {
					'url': data['url'],
					'params': data['post_data'],
					'redirect': redirect_url
				}

			else:
				return {
					'error': 'invalid_data',
				}

		else:
			return {
				'error': 'no_user',
			}

	def get_private_key(self, email, password):

		r = requests.post(
			"%s/%s" % (self.apiHost , 'auth/privateKey'),
			data={
				"email": email,
				"password": password
			},
			headers={
				'User-Agent': self._sm.userAgent,
				'X-Box-Id': self.boxId
			}
		)

		if r.status_code == 200:
			try:
				data = r.json()
			except:
				data = None

			if data and "private_key" in data:
				data_private_key = {}
				data_private_key["private_key"] = str(data['private_key'])
				if 'group_id' in data and data['group_id']:
					data_private_key['organization_id'] = str(data['organization_id'])
					data_private_key['group_id'] = str(data['group_id'])
				else:
					data_private_key['organization_id'] = None
					data_private_key['group_id'] = None
				return data_private_key

		elif r.status_code == 403:
			raise AstroPrintCloudInsufficientPermissionsException(r.json())

		elif r.status_code in [500, 503]:
			raise AstroPrintCloudTemporaryErrorException(r.status_code)

		return None

	def get_public_key(self, email, private_key):
		r = requests.post(
			"%s/%s" % (self.apiHost , 'auth/publicKey'),
			data={
				"email": email,
				"private_key": private_key
			},
			headers={'User-Agent': self._sm.userAgent}
		)

		try:
			data = r.json()
		except:
			data = None

		if data and "public_key" in data:
			return str(data["public_key"])
		else:
			return None

	def get_login_key(self):
		r = requests.get(
			"%s/%s" % (self.apiHost , 'auth/loginKey'),
			headers={'User-Agent': self._sm.userAgent},
			auth= self.hmacAuth
		)

		try:
			data = r.json()
		except:
			data = None

		return data

	def print_files(self, forceCloudSync = False):
		if self.cloud_enabled() and (self._print_file_store is None or forceCloudSync):
			self._sync_print_file_store()

		return json.dumps(self._print_file_store)

	def download_print_file(self, print_file_id, progressCb, successCb, errorCb, sentFromCloud = False):
		dm = downloadManager()
		markFile = sentFromCloud and self.settings.get(['clearFiles'])

		if dm.isDownloading(print_file_id):
			#We just return, there's already a download for this file in process
			#which means that the events will be issued for that one.
			return True

		fileManager = printerManager().fileManager

		# In case request generates an exception and never returns. We can check for None later
		r = None

		try:
			r = requests.get('%s/print-files/%s' % (self.apiHost, print_file_id), auth=self.hmacAuth)
			if r.status_code == 200:
				data = r.json()
			else:
				data = None
				self._logger.error('Unable to get print file [%s] info. HTTP ERROR: %d' % (print_file_id, r.status_code))
		except Exception as e:
			data = None
			self._logger.error('Unable to get print file [%s] info: %s' % (print_file_id, e) , exc_info = True)

		printFile = fileManager.getFileByCloudId(print_file_id)

		if printFile:
			self._logger.info('Print file %s is already on the box as %s' % (print_file_id, printFile))

			if data and "printFileName" in data:
				pm = printerManager()
				localPrintFileName = pm.fileManager.getPrintFileName(printFile)

				if data["printFileName"] != localPrintFileName:
					pm.fileManager.setPrintFileName(printFile, data["printFileName"])
					#update printFileName for this printFile in the collection
					if self._print_file_store:
						for x in self._print_file_store:
							if x['id'] == print_file_id:
								x['printFileName'] = data["printFileName"]
								break

			successCb(printFile, True)
			return True

		#The file wasn't there so let's go get it
		progressCb(1)

		destFile = None
		destFilename = None
		printFileName = None
		printer = None
		material = None
		quality = None
		image = None
		created = None

		if data and "download_url" in data and (("name" in data) or ("filename" in data)) and "info" in data:
			progressCb(2)

			if "filename" in data:
				destFilename = data['filename']
				printFileName = data["printFileName"]

			else:
				destFilename = printFileName = data['name']

			destFilename, destFileExt = os.path.splitext(destFilename)

			if destFileExt[1:].lower() not in fileManager.SUPPORTED_EXTENSIONS:
				return {"id": "wrong_file_type", "message": "The print file format is not compatible with the configured printer"}

			if "printer" in data:
				printer = data['printer']
			if "material" in data:
				material = data['material']
			if "quality" in data:
				quality = data['quality']
			if "image" in data:
				image = data['image']
			if "created" in data:
				created = data['created']

			destFile = fileManager.getAbsolutePath(destFilename + destFileExt, mustExist=False)

			if destFile:
				def onSuccess(pf, error):
					self._print_file_store = None
					successCb(pf, error)

				dm.startDownload({
					'downloadUrl': data["download_url"],
					'destFile': destFile,
					'printFileId': print_file_id,
					'printFileInfo': data['info'],
					'printFileName': printFileName,
					'printer': printer,
					'material': material,
					'quality': quality,
					'image': image,
					'created': created,
					'progressCb': progressCb,
					'successCb': onSuccess,
					'errorCb': errorCb,
					'sentFromCloud' : markFile
				})

				return True

		else:
			errorCb(destFile, 'Unable to download file')
			if r:
				if r.status_code == 403:
					return {"id": "no_permissions", "message": "Unable to retrieve file. Insufficient permissions"}

				else:
					return {"id": "invalid_data", "message": "Invalid data from server. Can't retrieve print file"}

			else:
				# When there was not even a response, it means the server couldn't be reached. DNS issue or network down
				return {"id": "server_unreachable", "message": "Can reach server to download file"}

	def manufacturers(self):
		try:
			r = requests.get( "%s/v2/manufacturers" % (self.apiHost), auth=self.hmacAuth )
			data = r.json()
		except Exception:
			data = None

		if data:
			return {'manufacturers': data}
		else:
			return { 'error': 'invalid_data' }

	def printerModels(self, manufacturer_id):
		try:
			r = requests.get( "%s/v2/manufacturers/%s/models" % (self.apiHost, manufacturer_id), auth=self.hmacAuth )
			data = r.json()
		except:
			data = None

		if data:
			return {'printer_models': data}
		else:
			return { 'error': 'invalid_data'}

	def printerModel(self, model_id):
		try:
			r = requests.get( "%s/v2/manufacturers/models/%s" % (self.apiHost, model_id), auth=self.hmacAuth )
			data = r.json()
		except:
			data = None

		if data:
			return {'printer_model': data}
		else:
			return { 'error': 'invalid_data'}

	def getPrintFile(self, cloudId):
		if not self._print_file_store:
			self._sync_print_file_store()

		if self._print_file_store:
			for x in self._print_file_store:
				if x['id'] == cloudId:
					return x
			else:
				return None
		else:
			return None

	def startPrintCapture(self, filename):
		data = {'name': filename}

		pm = printerManager()

		print_file_id = pm.fileManager.getFileCloudId(filename)
		print_job_id = pm.currentPrintJobId

		if print_file_id:
			data['print_file_id'] = print_file_id

		if print_job_id:
			data['print_job_id'] = print_job_id

		try:
			r = requests.post(
				"%s/prints" % self.apiHost,
				data= data,
				auth= self.hmacAuth
			)
			status_code = r.status_code
		except:
			status_code = 500

		if status_code == 201:
			data = r.json()
			return {
				"error": False,
				"print_id": data['print_id']
			}

		if status_code == 402:
			return {
				"error": "no_storage"
			}

		else:
			return {
				"error": "unable_to_create"
			}

	def updateBoxrouterData(self, data):
		if self.cloud_enabled():
			try:
				if data:
					r = requests.put("%s/astrobox/%s/update-boxrouter-data" % (self.apiHost, self.boxId),
						data=json.dumps(data),
						auth=self.hmacAuth,
						headers={'Content-Type': 'application/json'}
					)

					if r.status_code == 200:
						return r.json()
					if r.status_code == 400:
						self._logger.error("Bad updateBoxrouterData request (400). Response: %s" % r.text)
					if r.status_code == 404:
						self._logger.error("Request updateBoxrouterData not found (404). Response: %s" % r.text)
			except Exception as e:
				self._logger.error("Failed to send updateBoxrouterData request: %s" % e)
		return False

	def callFleetInfo(self):
		if networkManager().isOnline():
			self.getFleetInfo()
		else:
			self._eventManager.subscribe(Events.NETWORK_STATUS, self.getFleetInfo)

	def getFleetInfo(self, event = None, payload = None):
		if self.cloud_enabled():
			try:
				r = requests.get("%s/astrobox/%s/fleetinfo" % (self.apiHost, self.boxId),
						auth=self.hmacAuth
					)
				r.raise_for_status()
				data = r.json()
				self.updateFleetInfo(data['organization_id'], data['group_id'])
				data = {'orgId' : data['organization_id'], 'groupId' : data['group_id']}
				self._eventManager.fire(Events.FLEET_STATUS, data)

			except requests.exceptions.HTTPError as err:
				if (err.response.status_code == 401 or (self.hmacAuth.groupId and err.response.status_code == 404)):
					self._logger.info("Box is in a fleet group where user does not have permission, logout")
					#User could be alredy removed by Box Router
					loggedUser = self.settings.get(['cloudSlicer', 'loggedUser'])
					if loggedUser:
						self.remove_logged_user()
			except requests.exceptions.RequestException as e:
				self._logger.error(e)

	def uploadImageFile(self, print_id, imageBuf):
		try:
			m = MultipartEncoder(fields=[('file',('snapshot.jpg', imageBuf))])
			r = requests.post(
				"%s/prints/%s/image" % (self.apiHost, print_id),
				data= m,
				headers= {'Content-Type': m.content_type},
				auth= self.hmacAuth
			)
			m = None #Free the memory?
			status_code = r.status_code
		except:
			status_code = 500

		if status_code == 201:
			data = r.json()
			return data

		else:
			return None

	def print_job(self, id= None, print_file_id= None, print_file_name= None, status= 'started', reason= None, materialUsed= None):
		if self.cloud_enabled():
			try:
				if id:
					data = {'status': status}

					if reason:
						data['reason'] = reason

					if materialUsed:
						data['material_used'] = materialUsed

					r = requests.put("%s/printjobs/%s" % (self.apiHost, id),
						data=json.dumps(data),
						auth=self.hmacAuth,
						headers={'Content-Type': 'application/json'}
					)

				else:
					#create a print job
					data = {
						'box_id': self.boxId,
						'product_variant_id': softwareManager().data['variant']['id']
					}

					if not print_file_id and not print_file_name:
						self._logger.error('print_file_id and name are both missing in print_job')
						return False

					if print_file_id:
						data['print_file_id'] = print_file_id

					if print_file_name:
						data['name'] = print_file_name

					r = requests.post( "%s/printjobs" % self.apiHost, data= json.dumps(data), auth=self.hmacAuth, headers={'Content-Type': 'application/json'} )

				if r.status_code == 200:
					return r.json()

				if r.status_code == 400:
					self._logger.error("Bad print_job request (400). Response: %s" % r.text)

				else:
					self._logger.error("print_job request failed with status: %d" % r.status_code)

			except Exception as e:
				self._logger.error("Failed to send print_job request: %s" % e)

		return False

	def updateCancelReason(self, printJobId, reason):
		if (self.cloud_enabled()):
			try:
				r = requests.put("%s/printjobs/%s/add-reason" % (self.apiHost, printJobId),
					data=json.dumps(reason),
					auth=self.hmacAuth,
					headers={'Content-Type': 'application/json'}
				)

				if r.status_code == 200:
					return True

				if r.status_code == 400:
					self._logger.error("Unable to do updateCancelReason (400). Response: %s" % r.text)

				else:
					self._logger.error("updateCancelReason request failed with status: %d" % r.status_code)

			except Exception as e:
				self._logger.error("Failed to send updateCancelReason request: %s" % e)

		return False

	def _sync_print_file_store(self):
		if self.cloud_enabled():
			try:
				r = requests.get( "%s/print-files?format=%s" % (self.apiHost, printerManager().fileManager.fileFormat), auth=self.hmacAuth )
				self._print_file_store = r.json()
			except Exception as e:
				self._logger.error("Error syncing with cloud: %s" % e, exc_info = True)
