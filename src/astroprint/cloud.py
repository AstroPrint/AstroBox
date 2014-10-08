__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"

import requests
import hmac
import binascii
import uuid
import os
import json

from urllib import quote_plus
from os.path import splitext, split
from hashlib import sha256

from time import sleep

from requests_toolbelt import MultipartEncoder

from octoprint.settings import settings
from astroprint.software import softwareManager

from astroprint.boxrouter import boxrouterManager

# singleton
_instance = None

def astroprintCloud():
	global _instance
	if _instance is None:
		_instance = AstroPrintCloud()
	return _instance

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

		publicKey = self.settings.get(['cloudSlicer', 'publicKey'])
		privateKey = self.settings.get(['cloudSlicer', 'privateKey'])

		self.hmacAuth = HMACAuth(publicKey, privateKey,)
		self.apiHost = self.settings.get(['cloudSlicer', 'apiHost'])
		self.print_file_store = None
		self._sm = softwareManager()

	@staticmethod
	def cloud_enabled():
		s = settings()
		return s.get(['cloudSlicer', 'publicKey']) and s.get(['cloudSlicer', 'privateKey']) and s.get(['cloudSlicer', 'apiHost'])

	def signin(self, email, password):
		private_key = self.get_private_key(email, password)

		if private_key:
			public_key = self.get_public_key(email, private_key)

			if public_key:
				self.settings.set(["cloudSlicer", "privateKey"], private_key)
				self.settings.set(["cloudSlicer", "publicKey"], public_key)
				self.settings.set(["cloudSlicer", "email"], email)
				self.settings.save()
				boxrouterManager().boxrouter_connect()

				#let the singleton be recreated again, so new credentials are taken into use
				global _instance
				_instance = None

				return True

		return False

	def signout(self):
		self.settings.set(["cloudSlicer", "privateKey"], None)
		self.settings.set(["cloudSlicer", "publicKey"], None)
		self.settings.set(["cloudSlicer", "email"], None)
		self.settings.save()
		self.print_file_store = None
		boxrouterManager().boxrouter_disconnect()

		#let the singleton be recreated again, so credentials are forgotten
		global _instance
		_instance = None

	def get_upload_info(self, filePath):
		path, filename = split(filePath)
		path, fileExtension = splitext(filename)
		design_id = uuid.uuid4().hex
		s3_key = design_id + fileExtension

		try:
			#Get credentials to upload the file
			r = requests.get( "%s/designs/upload/params?key=%s" % (self.apiHost, s3_key), auth=self.hmacAuth )
			data = r.json()
		except:
			data = None

		if data:
			publicKey = self.settings.get(['cloudSlicer', 'publicKey'])
			privateKey = self.settings.get(['cloudSlicer', 'privateKey'])

			request = json.dumps({
				'design_id': design_id,
				's3_key': s3_key,
				'filename': filename
			})

			hashed = hmac.new(privateKey, request, sha256)
			signature = binascii.b2a_base64(hashed.digest())[:-1]

			redirect_url = "%s/design/uploaded?public_key=%s&req=%s&sig=%s" % (
				self.apiHost.replace('api', 'www'), 
				publicKey, 
				quote_plus(request), 
				quote_plus(signature))

			#url, post parameters, redirect Url
			return data['url'], data['post_data'], redirect_url
		else:
			return None, None, None

	def get_private_key(self, email, password):
		r = requests.post( "%s/%s" % (self.apiHost , 'auth/privateKey'),
						   data={
							"email": email,
							"password": password
						   },
						   headers={'User-Agent': self._sm.userAgent})

		try:
			data = r.json()
		except:
			data = None

		if data and "private_key" in data:
			return data["private_key"]
		else:
			return None		

	def get_public_key(self, email, private_key):
		r = requests.post( "%s/%s" % (self.apiHost , 'auth/publicKey'),
						   data={
							"email": email,
							"private_key": private_key
						   },
						   headers={'User-Agent': self._sm.userAgent})

		try:
			data = r.json()
		except:
			data = None

		if data and "public_key" in data:
			return data["public_key"]
		else:
			return None

	def start_slice_job(self, config, gcodePath, stlPath, procesingCb, completionCb):
		s = requests.Session()
		s.auth = self.hmacAuth

		upload_url, upload_data = self.get_upload_info(stlPath)

		if not upload_url:
			s.close()
			completionCb(stlPath, gcodePath, "Unable to obtaion creadentials to upload design to the slicer service.")
			return

		try:
			# Upload to s3

			m = MultipartEncoder(fields=upload_data.items() + [('file',(stlPath, open(stlPath, 'rb')))])
			r = requests.post( upload_url, data=m, headers={'Content-Type': m.content_type})
			m = None #Free the memory?
			status_code = r.status_code
		except: 
			status_code = 500

		if status_code > 204:
			s.close()
			completionCb(stlPath, gcodePath, "The design couldn't be uploaded to the slicer service.")
			return

		path, filename = split(stlPath)

		try:
			r = s.post( "%s/%s" % (self.apiHost, "designs/slice"), 
			data={
				"input_key": s3_key,
				"filename": filename
			})
			data = r.json()

		except:
			data = None

		if not data or "design_id" not in data:
			s.close()
			completionCb(stlPath, gcodePath, "There was an error creating slicing job.")
			return

		design_id = data['design_id']

		sleep(1)
		# Loop to watch for completion of the slicing job
		while True:
			try:
				r = s.get('%s/designs/%s' % (self.apiHost, design_id))
				data = r.json()
			except:
				data = None

			if data and "progress" in data and "status" in data:
				if data["status"] == 'failed':
					s.close()
					completionCb(stlPath, gcodePath, data["error"] if "error" in data else "Cloud slicer failed." )
					return

				procesingCb(min(data["progress"], 90))
				if data["progress"] >= 100 or data["status"] == 'finished':
					break

			else:
				s.close()
				completionCb(stlPath, gcodePath, "Slicing failed.")
				return

			sleep(2)

		try:
			r = s.get('%s/designs/%s/gcode/link' % (self.apiHost, design_id))
			data = r.json()
		except:
			data = None

		s.close()
		if data and "url" in data:
			r = requests.get(data["url"], stream=True)

			if r.status_code == 200:
				content_length = float(r.headers['Content-Length']);
				downloaded_size = 0.0

				with open(gcodePath, 'wb') as fd:
					for chunk in r.iter_content(524288): #0.5 MB
						downloaded_size += len(chunk)
						fd.write(chunk)
						procesingCb(90 + round((downloaded_size / content_length) * 10.0, 1))

				completionCb(stlPath, gcodePath)
				return

			else:
				r.close()

		completionCb(stlPath, gcodePath, "GCode file was not valid.")

	def print_files(self, forceCloudSync = False):
		if not self.print_file_store or forceCloudSync:
			try:
				r = requests.get( "%s/print-files" % self.apiHost, auth=self.hmacAuth )
				self.print_file_store = r.json()
			except:
				pass

		return json.dumps(self.print_file_store)	

	def download_print_file(self, print_file_id, progressCb, successCb, errorCb):
		progressCb(2)

		try:
			r = requests.get('%s/print-files/%s' % (self.apiHost, print_file_id), auth=self.hmacAuth)
			data = r.json()
		except:
			data = None

		destFile = None

		if data and "download_url" in data and "name" in data and "info" in data:
			progressCb(5)

			r = requests.get(data["download_url"], stream=True)

			if r.status_code == 200:
				from octoprint.server import gcodeManager

				content_length = float(r.headers['Content-Length']);
				downloaded_size = 0.0

				destFile = gcodeManager.getAbsolutePath(data['name'], mustExist=False)

				with open(destFile, 'wb') as fd:
					for chunk in r.iter_content(524288): #0.5 MB
						downloaded_size += len(chunk)
						fd.write(chunk)
						progressCb(5 + round((downloaded_size / content_length) * 95.0, 1))

				fileInfo = {
					'id': print_file_id,
					'info': data["info"]
				}

				successCb(destFile, fileInfo)
				return True;

			else:
				r.close()

		errorCb(destFile, 'Unable to download file')
		return False