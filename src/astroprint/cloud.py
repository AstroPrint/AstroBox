__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

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

class AstroPrintCloudException(Exception):
	pass

class AstroPrintCloudNoConnectionException(AstroPrintCloudException):
	#There no connection to the astroprint cloud
	pass

class HMACAuth(requests.auth.AuthBase):
	def __init__(self, publicKey, privateKey):
		self.publicKey = publicKey
		self.privateKey = privateKey

	def __call__(self, r):
		r.headers['User-Agent'] = softwareManager().userAgent
		sig_base = '&'.join((r.method, r.headers['User-Agent']))

		hashed = hmac.new(self.privateKey, sig_base, sha256)

		r.headers['X-Public'] = self.publicKey
		r.headers['X-Hash'] = binascii.b2a_base64(hashed.digest())[:-1]

		return r

class AstroPrintCloud(object):
	def __init__(self):
		self.settings = settings()
		self.hmacAuth = None

		self.tryingLoggingTimes = 0

		loggedUser = self.settings.get(['cloudSlicer', 'loggedUser'])
		if loggedUser:
			from octoprint.server import userManager

			user = userManager.findUser(loggedUser)

			if user and user.publicKey and user.privateKey:
				self.hmacAuth = HMACAuth(user.publicKey, user.privateKey)

		self.apiHost = self.settings.get(['cloudSlicer', 'apiHost'])
		self._print_file_store = None
		self._sm = softwareManager()
		self._logger = logging.getLogger(__name__)

	def cloud_enabled(self):
		return settings().get(['cloudSlicer', 'apiHost']) and self.hmacAuth

	def signin(self, email, password, hasSessionContext = True):
		from octoprint.server import userManager
		from astroprint.network.manager import networkManager
		user = None
		userLoggedIn = False

		online = networkManager().isOnline()

		if online:
			private_key = self.get_private_key(email, password)

			if private_key:
				public_key = self.get_public_key(email, private_key)

				if public_key:
					#Let's protect the box now:
					user = userManager.findUser(email)

					if user:
						userManager.changeUserPassword(email, password)
						userManager.changeCloudAccessKeys(email, public_key, private_key)
					else:
						user = userManager.addUser(email, password, public_key, private_key, True)

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
		from astroprint.network.manager import networkManager
		user = None
		userValidated = False

		online = networkManager().isOnline()

		if online:
			try:
				private_key = self.get_private_key(email, password)

				if private_key:
					public_key = self.get_public_key(email, private_key)

					if public_key:
						#Let's update the box now:
						user = userManager.findUser(email)
						if user:
							userManager.changeUserPassword(email, password)
							userManager.changeCloudAccessKeys(email, public_key, private_key)
						else:
							user = userManager.addUser(email, password, public_key, private_key, True)

						userValidated = True

					else:
						return False

				else:
					return False

			except ConnectionError as e:
				self._logger.error('Connection error when trying to validate password: %s' % e)

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
		from astroprint.network.manager import networkManager

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

	def get_upload_info(self, filePath):
		path, filename = split(filePath)
		path, fileExtension = splitext(filename)
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
			headers={'User-Agent': self._sm.userAgent}
		)

		try:
			data = r.json()
		except:
			data = None

		if data and "private_key" in data:
			return str(data["private_key"])
		else:
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

	def download_print_file(self, print_file_id, progressCb, successCb, errorCb):
		dm = downloadManager()

		if dm.isDownloading(print_file_id):
			#We just return, there's already a download for this file in process
			#which means that the events will be issued for that one.
			return True

		fileManager = printerManager().fileManager

		try:
			r = requests.get('%s/print-files/%s' % (self.apiHost, print_file_id), auth=self.hmacAuth)
			data = r.json()
		except Exception as e:
			data = None
			self._logger.error('Unable to get file info: %s' % e , exc_info = True)

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
		printFileName = None
		printer = None
		material = None
		quality = None
		image = None
		created = None

		if data and "download_url" in data and (("name" in data) or ("filename" in data)) and "info" in data:
			progressCb(2)

			if "filename" in data:
				destFile = fileManager.getAbsolutePath(data['filename'], mustExist=False)
				printFileName = data["printFileName"]

			else:
				destFile = fileManager.getAbsolutePath(data['name'], mustExist=False)
				printFileName = data["name"]

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

			destFile = fileManager.getAbsolutePath(data['name'], mustExist=False)

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
					'errorCb': errorCb
				})

				return True

		else:
			errorCb(destFile, 'Unable to download file')
			return False


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

	def print_job(self, id= None, print_file_id= None, print_file_name= None, status= 'started', reason= None, materialUsed= None ):
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
						'box_id': boxrouterManager().boxId,
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
