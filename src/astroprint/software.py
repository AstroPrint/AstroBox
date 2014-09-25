# coding=utf-8
__author__ = "Daniel Arroyo <daniel@3dagogo.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import yaml
import requests
import json
import subprocess
import threading
import logging

from tempfile import mkstemp
from sys import platform

from octoprint.settings import settings
from octoprint.events import eventManager, Events

# singleton
_instance = None

def softwareManager():
	global _instance
	if _instance is None:
		_instance = SoftwareManager()
	return _instance

class SoftwareUpdater(threading.Thread):
	def __init__(self, manager, versionData, progressCb, completionCb):
		super(SoftwareUpdater, self).__init__()
		self.vData = versionData
		self._manager = manager
		self._progressCb = progressCb
		self._completionCb = completionCb

	def run(self):
		self._progressCb(0.2, "Downloading release...")
		r = requests.get(self.vData["download_url"], stream=True, headers = self._manager._requestHeaders)

		if r.status_code == 200:
			releaseHandle, releasePath = mkstemp()

			content_length = float(r.headers['Content-Length']);
			downloaded_size = 0.0

			with os.fdopen(releaseHandle, "wb") as fd:
				for chunk in r.iter_content(250000):
					downloaded_size += len(chunk)
					fd.write(chunk)
					percent = round((downloaded_size / content_length), 2)
					self._progressCb(percent, "Downloading release (%d%%)" % (percent * 100) )

			if platform == "linux" or platform == "linux2":
				self._progressCb(percent, "Installing release. Please be patient..." )
				if subprocess.call(['dpkg', '-i', releasePath]) == 0:
					self._manager.data["version"]["major"] = self.vData['major']
					self._manager.data["version"]["minor"] = self.vData['minor']
					self._manager.data["version"]["build"] = self.vData['build']
					self._manager.data["version"]["date"] = self.vData['date']
					self._manager.data["platform"] = self.vData['platform']
					self._manager._save()

					os.remove(releasePath)

					if self.vData['force_setup']:
						#remove the config file
						os.remove(self._manager._settings._configfile)

					return self._completionCb(True)

			else:

				from time import sleep

				i=0.0
				while i<10:
					percent = i/10.0
					self._progressCb(percent, "Installation Progress Sim (%d%%)" % (percent * 100) )
					sleep(1)
					i+=1

				os.remove(releasePath)

				if self.vData['force_setup']:
					#remove the config file
					os.remove(self._manager._settings._configfile)

				return self._completionCb(True)
		else:
			self._manager._logger.error('Error performing software update info: %d' % r.status_code)
			r.close()

		self._completionCb(False)


class SoftwareManager(object):	
	def __init__(self):
		self._settings = settings()
		self._updater = None
		self._infoFile = self._settings.get(['software', 'infoFile']) or "%s/software.yaml" % os.path.dirname(self._settings._configfile)
		self._logger = logging.getLogger(__name__)

		self.forceUpdateInfo = None
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
			},
			"platform": None
		}

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

	@property
	def updatingRelease(self):
		if self._updater and self._updater.isAlive():
			return self._updater.vData
		else:
			return False

	def checkForcedUpdate(self):
		latestInfo = self.checkSoftwareVersion()
		if latestInfo and latestInfo['update_available'] and latestInfo['release']['forced'] and not latestInfo['is_current']:
			import datetime
			self._logger.warn('New version %d.%d(%s) is forced and available for this box.' % (
				latestInfo['release']['major'],
				latestInfo['release']['minor'],
				latestInfo['release']['build']
			))
			if latestInfo['release']['date']:
				latestInfo['release']['date'] = datetime.datetime.strptime(latestInfo['release']['date'], "%Y-%m-%d %H:%M:%S").date()
			self.forceUpdateInfo = latestInfo['release']

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
					'variant': self.data['variant']['id'],
					'platform': self.data['platform']
				}),
				auth = self._checkAuth(),
				headers = self._requestHeaders
			)

			if r.status_code != 200:
				self._logger.error('Error getting software release info: %d.' % r.status_code)
				data = None
			else:
				data = r.json()

		except Exception as e:
			self._logger.error('Error getting software release info: %s' % e)
			data = None

		if data and data['update_available']:
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

				if data and 'download_url' in data and data['platform'] == self.data['platform']:
					def progressCb(progress, message=None):
						eventManager().fire(Events.SOFTWARE_UPDATE, {
							'completed': False,
							'progress': progress,
							'message': message
						})

					def completionCb(success):
						self._updater = None
						eventManager().fire(Events.SOFTWARE_UPDATE, {
							'completed': True,
							'success': success
						})
						if success:
							self.forceUpdateInfo = None

					self._updater = SoftwareUpdater(self, data, progressCb, completionCb)
					self._updater.start()
					return True

				else:
					self._logger.error('Error updating software release info: %d' % r.status_code)


		except Exception as e:
			self._logger.error('Error updating software release info: %s' % e)
			pass

		return False

	def restartServer(self):
		if platform == "linux" or platform == "linux2":
			from astroprint.boxrouter import boxrouterManager
			from octoprint.server import printer

			#let's be nice about shutthing things down
			br = boxrouterManager()

			br.boxrouter_disconnect()
			printer.disconnect()

			actions = self._settings.get(["system", "actions"])
			for a in actions:
				if a['action'] == 'astrobox-restart':
					subprocess.call(a['command'].split(' '))
					return True

			subprocess.call(['restart', 'astrobox'])

		return True

	def _checkAuth(self):
		privateKey = self._settings.get(['cloudSlicer', 'privateKey'])
		publicKey = self._settings.get(['cloudSlicer', 'publicKey'])
		if self._settings.getBoolean(['software', 'useUnreleased']) and privateKey and publicKey:
			from astroprint.cloud import HMACAuth

			return HMACAuth(publicKey, privateKey)

		else:
			return None

