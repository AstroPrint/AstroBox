# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import yaml
import requests
import json
import subprocess

from tempfile import mkstemp

from sys import platform

from octoprint.settings import settings

class SoftwareManager(object):	
	def __init__(self):
		self._settings = settings()
		self.data = {
			"version": {
				"major": 0,
				"minor": 0,
				"build": u'0',
				"date": None
			},
			"variant": {
				"id": None,
				"name": 'AstroBox'
			}
		}

		self._infoFile = self._settings.get(['software', 'infoFile']) or "%s/software.yaml" % os.path.dirname(self._settings._configfile)
		if not os.path.isfile(self._infoFile):
			open(self._infoFile, 'w').close()

		if self._infoFile:
			config = None
			with open(self._infoFile, "r") as f:
				config = yaml.safe_load(f)

			def merge_dict(a,b):
				for key in b:
					if isinstance(b[key], dict):
						merge_dict(a[key], b[key])
					else:
						a[key] = b[key]

			if config:
				merge_dict(self.data, config)

		self._requestHeaders = {
			'User-Agent': self.userAgent
		}

	@property
	def versionString(self):
		return '%s - v%d.%d(%s)' % (
			self.data['variant']['name'],
			self.data['version']['major'], 
			self.data['version']['minor'], 
			self.data['version']['build'])

	@property
	def userAgent(self):
		return "Astrobox; version:%d.%d(%s); variant: %s; platform: [%s]" % (
			self.data['version']['major'], self.data['version']['minor'], self.data['version']['build'],
			self.data['variant']['name'],
			subprocess.check_output('uname -v', shell=True)[:-1]
		)

	def _save(self, force=False):
		with open(self._infoFile, "wb") as infoFile:
			yaml.safe_dump(self.data, infoFile, default_flow_style=False, indent="    ", allow_unicode=True)

	def checkSoftwareVersion(self):
		try:
			r = requests.post('%s/astrobox/software/check' % self._settings.get(['cloudSlicer','apiHost']), data=json.dumps({
					'current': [
						self.data['version']['major'], 
						self.data['version']['minor'],
						self.data['version']['build']
					],
					'variant': self.data['variant']['id']
				}),
				auth = self._checkAuth(),
				headers = self._requestHeaders
			)

			if r.status_code != 200:
				data = None
			else:
				data = r.json()

		except Exception as e:
			data = None

		if data:
			#check if it's the same one we have installed
			data['is_current'] = data['release']['major'] == int(self.data['version']['major']) and data['release']['minor'] == int(self.data['version']['minor']) and data['release']['build'] == self.data['version']['build']

		return data

	def updateSoftwareVersion(self, data):
		try:
			r = requests.get(
				'%s/astrobox/software/release/%s' % (self._settings.get(['cloudSlicer','apiHost']), data['release_id']),
				auth = self._checkAuth(),
				headers = self._requestHeaders
			)

			if r.status_code == 200:
				data = r.json()

				if data and 'download_url' in data:
					r = requests.get(data["download_url"], stream=True, headers = self._requestHeaders)

					if r.status_code == 200:
						releaseHandle, releasePath = mkstemp()

						with os.fdopen(releaseHandle, "wb") as fd:
							for chunk in r.iter_content(250000):
								fd.write(chunk)
								#progressCb(5 + round((downloaded_size / content_length) * 95.0, 1))

						#successCb(destFile, fileInfo)

						if platform == "linux" or platform == "linux2":
							if subprocess.call(['dpkg', '-i', releasePath]) == 0:
								self.data["version"]["major"] = data['major']
								self.data["version"]["minor"] = data['minor']
								self.data["version"]["build"] = data['build']
								self.data["version"]["date"] = data['date']
								self._save()

								os.remove(releasePath)

								if data['force_setup']:
									#remove the config file
									os.remove(self._settings._configfile)

								return True

						else:
							os.remove(releasePath)

							if data['force_setup']:
								#remove the config file
								os.remove(self._settings._configfile)

							return True;

					else:
						r.close()
						#errorCb(destFile, 'Unable to download file')

		except Exception as e:
			pass

		return False

	def restartServer(self):
		if platform == "linux" or platform == "linux2":
			subprocess.call(['restart', 'astrobox'])

	def _checkAuth(self):
		privateKey = self._settings.get(['cloudSlicer', 'privateKey'])
		publicKey = self._settings.get(['cloudSlicer', 'publicKey'])
		if self._settings.getBoolean(['software', 'useUnreleased']) and privateKey and publicKey:
			from astroprint.cloud import HMACAuth

			return HMACAuth(publicKey, privateKey)

		else:
			return None

