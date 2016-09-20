# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

# singleton
_instance = None

def softwareManager():
	global _instance
	if _instance is None:
		_instance = SoftwareManager()
	return _instance

import os
import yaml
import requests
import json
import subprocess
import threading
import logging
import time

from tempfile import mkstemp
from sys import platform

from flask.ext.login import current_user

from octoprint.settings import settings
from octoprint.events import eventManager, Events

if platform != 'darwin':
	import apt.debfile
	import apt.progress.base
	import apt_pkg

	class DepsDownloadProgress(apt.progress.base.AcquireProgress):
		def __init__(self, progressCb, completionCb):
			super(DepsDownloadProgress, self).__init__()

			self._progressCb = progressCb
			self._completionCb = completionCb
			self._logger = logging.getLogger(__name__)

		def pulse(self, owner):
			#self._logger.info( "Fetching depedencies progress [ %.2f %% ]" % ( ( float(self.current_items) / float(self.total_items) ) * 100 ) )
			self._progressCb("deps_download", ( float(self.current_items) / float(self.total_items) ) )
			return True

		def done(self, item):
			#super(DepsDownloadProgress, self).done(item)
			self._logger.info("[%s] fetched" % item.shortdesc)

		def fail(self, item):
			super(DepsDownloadProgress, self).fail(item)
			self._logger.error("Error fetching dependency [%s]" % item.shortdesc)
			self._completionCb(False)


	class DepsInstallProgress(apt.progress.base.InstallProgress):
		def __init__(self, progressCb, completionCb):
			super(DepsInstallProgress, self).__init__()

			self._progressCb = progressCb
			self._completionCb = completionCb
			self._logger = logging.getLogger(__name__)

		def start_update(self):
			self._logger.info("Dependency installation started")
			self._progressCb("deps_install", 0.0 )

		def error(self, pkg, message):
			self._logger.error("Error during dependency [%s] installation: %s" % (pkg, message))
			self._completionCb(False)

		def status_change(self, pkg, percent, status):
			#self._logger.info("Dependency installation progress [%.2f %%] - %s" % (percent, status))
			self._progressCb("deps_install", ( percent / 100 ) )

		def finish_update(self):
			self._logger.info("Finished installing dependencies")
			self._progressCb("deps_install", 1.0 )


	class UpdateProgress(apt.progress.base.InstallProgress):
		def __init__(self, progressCb, completionCb):
			super(UpdateProgress, self).__init__()

			self._progressCb = progressCb
			self._completionCb = completionCb
			self._logger = logging.getLogger(__name__)
			self._errors = False

		def start_update(self):
			self._logger.info("Software Update started")
			self._progressCb("release_install", 0.2)

		def error(self, pkg, message):
			self._logger.error("Error during install [%s]" % message)
			self._completionCb(message)
			self._errors = True

		def processing(self, pkg, stage):
			if stage == 'upgrade':
				self._progressCb("release_install", 0.5)
			elif stage == 'configure':
				self._progressCb("release_configure", 0.5)
			elif stage == 'trigproc':
				self._progressCb("release_finalize", 0.0)

		def finish_update(self):
			if not self._errors:
				self._progressCb("release_finalize", 1.0, "Restarting. Please wait...")
				self._logger.info("Software Update completed succesfully")
				self._completionCb()

	class CacheUpdateFetchProgress(apt.progress.base.AcquireProgress):
		def __init__(self, progressCb, completionCb):
				super(CacheUpdateFetchProgress, self).__init__()

				self._progressCb = progressCb
				self._completionCb = completionCb
				self._logger = logging.getLogger(__name__)
				self._errors = False
				self._lastCurrentReported = None
				self._lastTotalReported = None

		def pulse(self, owner):
			if self.current_items != self._lastCurrentReported or self.total_items != self._lastTotalReported:
				self._progressCb("sources_update", float(self.current_items) / float(self.total_items))
				self._logger.info("Update progress item %d of %d" % (self.current_items, self.total_items))
				self._lastCurrentReported = self.current_items
				self._lastTotalReported = self.total_items

			return True

class SoftwareUpdater(threading.Thread):
	def __init__(self, manager, versionData, progressCb, completionCb):
		super(SoftwareUpdater, self).__init__()
		self.vData = versionData
		self._manager = manager
		self._progressCb = progressCb
		self._completionCb = completionCb
		self._logger = logging.getLogger(__name__)

	def run(self):
		#We need to give the UI a chance to update before starting so that the message can be sent...
		self._progressCb("download", 0.0, "Starting download...")
		time.sleep(2)
		r = requests.get(self.vData["download_url"], stream=True, headers = self._manager._requestHeaders)

		if r.status_code == 200:
			releaseHandle, releasePath = mkstemp()

			content_length = float(r.headers['Content-Length']);
			downloaded_size = 0.0

			self._logger.info('Downloading release.')
			with os.fdopen(releaseHandle, "wb") as fd:
				for chunk in r.iter_content(150000):
					downloaded_size += len(chunk)
					fd.write(chunk)
					self._progressCb("download", round((downloaded_size / content_length), 2))

			self._logger.info('Release downloaded.')
			if platform == "linux" or platform == "linux2":
				self._progressCb("download", 1.0 , "Release downloaded. Preparing...")
				time.sleep(0.5) #give the message a chance to be sent

				def completionCb(error = None):
					if os.path.isfile(releasePath):
						os.remove(releasePath)

					if error:
						self._completionCb(False)
					else:
						if self.vData['force_setup']:
							#remove the config file
							os.remove(self._manager._settings._configfile)

						self._completionCb(True)

				try:
					cache = apt.Cache()
					cache.update(CacheUpdateFetchProgress(self._progressCb, completionCb), 2000000)
					cache.open()
					cache.commit()

					pkg = apt.debfile.DebPackage(releasePath)
					self._progressCb("deps_download", 0.0, "Checking software package. Please be patient..." )

					pkg.check()

				except Exception as e:
					self._logger.error('There was a problem with update package: \n %s' % e)
					completionCb(True)
					return

				if pkg.missing_deps:
					cache.open()

					with cache.actiongroup():
						for dep in pkg.missing_deps:
							self._logger.info("Marking dependency [%s] to be installed." % dep)
							cache[dep].mark_install()

					self._progressCb("deps_download", 0.0)
					try:
						cache.commit(DepsDownloadProgress(self._progressCb, completionCb), DepsInstallProgress(self._progressCb, completionCb))
						self._logger.info("%d Dependencies installed" % len(pkg.missing_deps))

					except Exception as e:
						self._logger.error('There was a problem installing dependencies: \n %s' % e)
						completionCb(True)
						return

					self._progressCb("release_install", 0.0)

				pkg.install(UpdateProgress(self._progressCb, completionCb))

			else:
				i=0.0
				while i<10:
					percent = i/10.0
					self._progressCb("release_install", percent, "Installation Progress Sim (%d%%)" % (percent * 100) )
					time.sleep(1)
					i+=1

				os.remove(releasePath)

				if self.vData['force_setup']:
					#remove the config file
					os.remove(self._manager._settings._configfile)

				return self._completionCb(True)
		else:
			self._manager._logger.error('Error performing software update info: %d' % r.status_code)
			r.close()

class SoftwareManager(object):
	# Download Phase      start   end   message
	updatePhaseProgressInfo = {
		"download":       (0.0, 0.2,  "Downloading release..."),
		"sources_update":     (0.21,  0.4,  "Updating dependency list..."),
		"deps_download":    (0.41,  0.6,  "Downloading dependencies..."),
		"deps_install":     (0.61,  0.75, "Installing dependencies..."),
		"release_install":    (0.76,  0.85, "Upgrading software..."),
		"release_configure":  (0.86,  0.95, "Configuring..."),
		"release_finalize":   (0.96,  1.0,  "Finalizing")
	}

	softwareCheckInterval = 86400 #1 day

	def __init__(self):
		self._settings = settings()
		self._updater = None
		self._infoFile = self._settings.get(['software', 'infoFile']) or "%s/software.yaml" % os.path.dirname(self._settings._configfile)
		self._logger = logging.getLogger(__name__)

		self.lastCompletionPercent = None
		self.lastMessage = None

		self.forceUpdateInfo = None
		self.data = {
			"version": {
				"major": 0,
				"minor": 0,
				"build": u'0',
				"date": None,
				"commit": None
			},
			"variant": {
				"id": None,
				"name": 'AstroBox'
			},
			"platform": 'pcduino'
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
	def commit(self):
		return self.data['version']['commit']

	@property
	def platform(self):
		return self.data['platform']

	@property
	def variant(self):
		return self.data['variant']

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

	@property
	def shouldCheckForNew(self):
		return self._settings.get(["software", "lastCheck"]) < ( time.time() - self.softwareCheckInterval )

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
		apiHost = self._settings.get(['cloudSlicer','apiHost'])
		if not apiHost:
			self._logger.error('cloudSlicer.apiHost not present in config file.')
			return None

		try:
			r = requests.post('%s/astrobox/software/check' % apiHost, data=json.dumps({
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
					def progressCb(phase, progress, message=None):
						phaseData = self.updatePhaseProgressInfo[phase]
						spread = phaseData[1] - phaseData[0]
						globalProgress = phaseData[0] + progress * spread
						message = message or phaseData[2]

						if phaseData:
							eventManager().fire(Events.SOFTWARE_UPDATE, {
								'completed': False,
								'progress': globalProgress,
								'message': message
							})

							self.lastCompletionPercent = globalProgress
							self.lastMessage = message

					def completionCb(success):
						eventManager().fire(Events.SOFTWARE_UPDATE, {
							'completed': True,
							'success': success
						})

						if success:
							self.forceUpdateInfo = None
							#schedule a restart

							def tryRestart():
								if not self.restartServer():
									eventManager().fire(Events.SOFTWARE_UPDATE, {
										'completed': True,
										'progress': 1,
										'success': False,
										'message': 'Unable to restart'
									})

							threading.Timer(1, tryRestart).start()


					self.lastCompletionPercent = None
					self.lastMessage = None

					self._updater = SoftwareUpdater(self, data, progressCb, completionCb)
					self._updater.start()
					return True

				else:
					self._logger.error('Invalid data returned by server:')
					self._logger.error(data)

			else:
				self._logger.error('Error updating software release info. Server returned: %d' % r.status_code)

		except Exception as e:
			self._logger.error('Error updating software release info: %s' % e)

		return False

	def restartServer(self):
		if platform == "linux" or platform == "linux2":
			actions = self._settings.get(["system", "actions"])
			for a in actions:
				if a['action'] == 'astrobox-restart':
					#Call to Popen will start the restart command but return inmediately before it completes
					threading.Timer(1.0, subprocess.Popen, [a['command'].split(' ')]).start()
					self._logger.info('Restart command scheduled')

					from astroprint.boxrouter import boxrouterManager
					from astroprint.printer.manager import printerManager
					from astroprint.camera import cameraManager
					from astroprint.network.manager import networkManagerShutdown

					#let's be nice about shutthing things down
					boxrouterManager().boxrouter_disconnect()
					printerManager().disconnect()
					cameraManager().close_camera()
					networkManagerShutdown()

					return True

			return False

		return True

	def sendLogs(self, ticketNo=None, message=None):
		import zipfile

		from astroprint.boxrouter import boxrouterManager
		from tempfile import gettempdir

		try:
			boxId = boxrouterManager().boxId

			#Create the zip file
			zipFilename = '%s/%s-logs.zip' % (gettempdir(), boxId)
			zipf = zipfile.ZipFile(zipFilename, 'w')

			for root, dirs, files in os.walk(self._settings.getBaseFolder("logs")):
				for file in files:
					zipf.write(os.path.join(root, file), file)

			zipf.close()

		except Exception as e:
			self._logger.error('Error while zipping logs: %s' % e)
			return False

		zipf = open(zipFilename, 'rb')

		#send the file to the server
		r = requests.post(
			'%s/astrobox/software/logs' % (self._settings.get(['cloudSlicer','apiHost'])),
			data = { 'ticket': ticketNo, 'message': message, 'boxId': boxId},
			files = {'file': (zipFilename, zipf)},
			auth = self._checkAuth(),
			headers = self._requestHeaders
		)

		zipf.close()

		#remove the file
		os.remove(zipFilename)

		if r.status_code == 200:
			return True
		else:
			self._logger.error('Error while sending logs: %d' % r.status_code)
			return False

	def clearLogs(self):
		activeLogFiles = ['astrobox.log', 'serial.log']

		logsDir = self._settings.getBaseFolder("logs")

		# first delete all old logs
		for f in os.listdir(logsDir):
			path = os.path.join(logsDir, f)

			if os.path.isfile(path) and f not in activeLogFiles:
				os.unlink(path)

		# then truncate the currently used one
		for f in activeLogFiles:
			with open(os.path.join(logsDir,f), 'w'):
				pass

		return True

	def _checkAuth(self):
		if current_user and current_user.is_authenticated and not current_user.is_anonymous:
			privateKey = current_user.privateKey
			publicKey = current_user.publicKey

			if privateKey and publicKey:
				from astroprint.cloud import HMACAuth

				return HMACAuth(publicKey, privateKey)

		return None

