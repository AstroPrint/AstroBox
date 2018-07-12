# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

# singleton
_instance = None

def softwareManager():
	global _instance
	if _instance is None:
		_instance = SoftwareManager()
	return _instance

import os
import glob
import yaml
import requests
import json
import subprocess
import threading
import logging
import time
import platform
import re
import datetime

from tempfile import mkstemp
from sys import platform as platformStr

from flask_login import current_user

from octoprint.settings import settings
from octoprint.events import eventManager, Events

from astroprint.boxrouter import boxrouterManager

if platformStr != 'darwin':
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
				self._progressCb("release_finalize", 1.0, "Finalizing package...")
				self._logger.info("Software Package updated succesfully")
				self._completionCb()

	class CacheUpdateFetchProgress(apt.progress.base.AcquireProgress):
		def __init__(self, progressCb):
				super(CacheUpdateFetchProgress, self).__init__()

				self._progressCb = progressCb
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
	updatePhaseProgressInfo = {
		"download":       		(0.0,		0.25, "Downloading package..."),
		"sources_update":     (0.26,  0.4,  "Updating dependency list..."),
		"deps_download":    	(0.41,  0.6,  "Downloading dependencies..."),
		"deps_install":     	(0.61,  0.75, "Installing dependencies..."),
		"release_install":    (0.76,  0.85, "Upgrading package..."),
		"release_configure":  (0.86,  0.96, "Configuring Package..."),
		"release_finalize": 	(0.96,  1.0,	"Finalizing package...")
	}

	def __init__(self, manager, versionData, progressCb, completionCb):
		super(SoftwareUpdater, self).__init__()
		self.vData = versionData
		self._manager = manager
		self._progressCb = progressCb
		self._completionCb = completionCb
		self._logger = logging.getLogger(__name__)
		self._currentPackage = 0
		self._pkgCount = len(versionData)
		self._pkgPrgSpread = 1.0 / self._pkgCount
		self._lastPkgPrgEnd = 0
		self._cache = None
		self._stop = False

	def stop(self):
		self._stop = True

	def run(self):
		#We need to give the UI a chance to update before starting so that the message can be sent...
		self._progressCb("download", 0.0, "Starting...")
		#disconnect from the cloud during software upgrade. The reboot will take care of reconnect
		boxrouterManager().boxrouter_disconnect()

		time.sleep(2)
		self._installNextPackage()

	def _installNextPackage(self):
		if not self._stop:
			self._installPackage(self.vData[self._currentPackage])

	def _installPackage(self, relData):
		r = requests.get(relData['download_url'], stream=True, headers = self._manager._requestHeaders)

		if r.status_code == 200:
			releaseHandle, releasePath = mkstemp()

			content_length = float(r.headers['Content-Length'])
			downloaded_size = 0.0

			self._logger.info('Downloading release.')
			with os.fdopen(releaseHandle, "wb") as fd:
				for chunk in r.iter_content(150000):
					downloaded_size += len(chunk)
					fd.write(chunk)
					self._onProgress("download", round((downloaded_size / content_length), 2))

			self._logger.info('Release downloaded.')

			if "linux" in platformStr:
				self._onProgress("download", 1.0 , "Release downloaded. Preparing...")
				time.sleep(0.5) #give the message a chance to be sent

				def completionCb(error = None):
					if os.path.isfile(releasePath):
						os.remove(releasePath)

					if error:
						self._onCompleted(False)
					else:
						if relData['force_setup']:
							#remove the config file
							os.remove(self._manager._settings._configfile)

						self._onCompleted(True)

				try:
					# We should only update the cache once.
					if self._cache is None:
						self._cache = apt.Cache()
						self._cache.update(CacheUpdateFetchProgress(self._onProgress), 2000000)
						self._cache.open()
						self._cache.commit()

					pkg = apt.debfile.DebPackage(releasePath)
					self._onProgress("deps_download", 0.0, "Checking software package. Please be patient..." )

					pkg.check()

				except Exception as e:
					self._logger.error('There was a problem with update package: \n %s' % e)
					completionCb(True)
					return

				if pkg.missing_deps:
					self._cache.open()

					with self._cache.actiongroup():
						for dep in pkg.missing_deps:
							self._logger.info("Marking dependency [%s] to be installed." % dep)
							self._cache[dep].mark_install()

					self._onProgress("deps_download", 0.0)
					try:
						self._cache.commit(DepsDownloadProgress(self._onProgress, completionCb), DepsInstallProgress(self._onProgress, completionCb))
						self._logger.info("%d Dependencies installed" % len(pkg.missing_deps))

					except Exception as e:
						self._logger.error('There was a problem installing dependencies: \n %s' % e)
						completionCb(True)
						return

					self._onProgress("release_install", 0.0)

				pkg.install(UpdateProgress(self._onProgress, completionCb))

			else:
				phases = ["sources_update", "deps_download", "deps_install", "release_install", "release_configure", "release_finalize"]

				for phase in phases:
					i = 0.0
					while i <= 10:
						percent = i/10.0
						self._onProgress(phase, percent)
						time.sleep(0.1)
						i += 1

				os.remove(releasePath)

				if relData['force_setup']:
					#remove the config file
					os.remove(self._manager._settings._configfile)

				return self._onCompleted(True)

		else:
			self._manager._logger.error('Error performing software update info: %d' % r.status_code)
			r.close()

	def _onProgress(self, phase, progress, message=None):
		phaseData = self.updatePhaseProgressInfo[phase]
		spread = phaseData[1] - phaseData[0]
		pkgProgress = phaseData[0] + progress * spread

		self._progressCb(phase, self._lastPkgPrgEnd + ( pkgProgress * self._pkgPrgSpread ), message or phaseData[2])

	def _onCompleted(self, success):
		if success:
			self._currentPackage += 1
			self._lastPkgPrgEnd += self._pkgPrgSpread

			if self._currentPackage < self._pkgCount:
				self._installNextPackage()
			else:
				self._progressCb("release_finalize", 1.0, "Update Completed")
				self._logger.info("Software Update completed succesfully")
				self._completionCb(True)
		else:
			self._completionCb(False)

class SoftwareManager(object):
	softwareCheckInterval = 86400 #1 day

	def __init__(self):
		self._settings = settings()
		self._updater = None
		self._infoDir = self._settings.get(['software', 'infoDir']) or os.path.join(os.path.dirname(self._settings._configfile), 'software')
		self._logger = logging.getLogger(__name__)
		self._wasBadShutdown = None
		self._badShutdownShown = False
		self._status = 'idle'
		self._releases = None

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
			"manufacturer_pkg_id": None,
			"platform": 'pcduino',
			"additional": []
		}

		if self._infoDir:
			config = None

			def merge_dict(a,b):
				for key in b:
					if isinstance(b[key], dict):
						merge_dict(a[key], b[key])
					else:
						a[key] = b[key]

			with open(os.path.join(self._infoDir,'software.yaml'), "r") as f:
				config = yaml.safe_load(f)

			merge_dict(self.data, config)

			#Check if there's a manufacturer package
			manufacturerFile = os.path.join(self._infoDir,'manufacturer.yaml')
			if os.path.isfile(manufacturerFile):
				with open(manufacturerFile, "r") as f:
					config = yaml.safe_load(f)

				self.data['additional'].append(config)
				self.data['manufacturer_pkg_id'] = config['package']['id']

			additionalPath = os.path.join(self._infoDir, 'additional')
			if os.path.isdir(additionalPath):
				for f in glob.glob(os.path.join(additionalPath, "*.yaml")):
					with open(f, "r") as f:
						config = yaml.safe_load(f)

					if config:
						self.data['additional'].append(config)

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
	def mfPackageId(self):
		return self.data['manufacturer_pkg_id']

	@property
	def userAgent(self):
		return "Astrobox; version:%d.%d(%s); variant: %s; platform: [%s]" % (
			self.data['version']['major'], self.data['version']['minor'], self.data['version']['build'],
			self.data['variant']['name'],
			subprocess.check_output('uname -v', shell=True)[:-1]
		)

	@property
	def updatingReleases(self):
		if self._releases:
			return self._releases
		else:
			return False

	@property
	def status(self):
		return self._status

	@property
	def shouldCheckForNew(self):
		return self._settings.get(["software", "lastCheck"]) < ( time.time() - self.softwareCheckInterval )

	@property
	def wasBadShutdown(self):
		if self._wasBadShutdown is None:
			flagFilename = "%s/improper-shutdown" % os.path.dirname(self._settings._configfile)
			if os.path.exists(flagFilename):
				self._wasBadShutdown = True
				os.unlink(flagFilename)
			else:
				self._wasBadShutdown = False

		return self._wasBadShutdown

	@property
	def badShutdownShown(self):
		if self._badShutdownShown:
			return True
		else:
			self._badShutdownShown = True
			return False

	def checkForcedUpdate(self):
		latestInfo = self.checkSoftwareVersion()

		if latestInfo and latestInfo['update_available']:
			for package in latestInfo['releases']:
				if package['update_available'] and package['release']['forced'] and not package['is_current']:
					self._logger.warn('New version %d.%d(%s) is forced and available for this box.' % (
						package['release']['major'],
						package['release']['minor'],
						package['release']['build']
					))
					if package['release']['date']:
						package['release']['date'] = datetime.datetime.strptime(package['release']['date'], "%Y-%m-%d %H:%M:%S").date()
					self.forceUpdateInfo = package['release']
					return #When we find the first force that's enough

	def checkSoftwareVersion(self):
		apiHost = self._settings.get(['cloudSlicer','apiHost'])
		if not apiHost:
			self._logger.error('cloudSlicer.apiHost not present in config file.')
			return None

		try:
			data = {
				'update_available': False,
				'releases': []
			}

			for package in ([self.data] + self.data['additional']):
				versionData = {
					'current': [
						package['version']['major'],
						package['version']['minor'],
						package['version']['build']
					],
					'channel': self._settings.getInt(['software', 'channel'])
				}

				if 'variant' in package:
					versionData['variant'] = package['variant']['id']
					versionData['platform'] = package['platform']
					versionData['manufacturer_pkg_id'] = self.data['manufacturer_pkg_id']
				elif 'package' in package:
					versionData['variant'] = self.data['variant']['id']
					versionData['package'] = package['package']['id']

				r = requests.post('%s/astrobox/software/check' % apiHost, data=json.dumps(versionData),
					auth = self._checkAuth(),
					headers = self._requestHeaders
				)

				if r.status_code != 200:
					self._logger.error('Error getting software release info: %d.' % r.status_code)
					return None
				else:
					packageData = r.json()
					packageData['name'] = package['variant']['name'] if 'variant' in package else package['package']['name']

					if packageData['update_available']:
						#check if it's the same one we have installed
						packageData['is_current'] = packageData['release']['major'] == int(package['version']['major']) and packageData['release']['minor'] == int(package['version']['minor']) and packageData['release']['build'] == package['version']['build']
						if not packageData['is_current']:
							data['update_available'] = True

					data['releases'].append(packageData)

		except Exception as e:
			self._logger.error('Error getting software release info: %s' % e)
			return None

		return data

	def updateSoftware(self, releases):
		self._status = 'updating'
		self._releases = releases
		releaseInfo = []
		platforms = {
			self.data['variant']['id']: self.data['platform']
		}
		platforms.update({p['variant']['id']: p['platform'] for p in self.data['additional'] if 'platform' in p})

		for rel in releases:
			try:
				r = requests.get(
					'%s/astrobox/software/release/%s' % (self._settings.get(['cloudSlicer','apiHost']), rel),
					auth = self._checkAuth(),
					headers = self._requestHeaders
				)

				if r.status_code == 200:
					data = r.json()

					if data and 'download_url' in data and 'platform' in data and 'variant' in data and 'id' in data['variant']:

						if data['platform'] is None or ( data['variant']['id'] in platforms and data['platform'] == platforms[data['variant']['id']]):
							releaseInfo.append(data)

						else:
							self._logger.error('Invalid Platform: %s' % data['platform'])
							self._status = 'failed'
							return False

					else:
						self._logger.error('Invalid Server response:')
						self._logger.error(data)
						self._status = 'failed'
						return False

				else:
					self._logger.error('Error updating software release info. Server returned: %d' % r.status_code)
					self._status = 'failed'
					return False

			except Exception as e:
				self._logger.error('Error updating software release info: %s' % e, exc_info = True)
				self._status = 'failed'
				return False

		if releaseInfo:
			def progressCb(phase, progress, message):
				eventManager().fire(Events.SOFTWARE_UPDATE, {
					'completed': False,
					'progress': progress,
					'status': self._status,
					'message': message
				})

				self.lastCompletionPercent = progress
				self.lastMessage = message

			def completionCb(success):
				if success:
					self.forceUpdateInfo = None
					self._status = 'done'
				else:
					self._status = 'failed'

				eventManager().fire(Events.SOFTWARE_UPDATE, {
					'completed': True,
					'status': self._status,
					'success': success
				})

			self.lastCompletionPercent = None
			self.lastMessage = None

			self._updater = SoftwareUpdater(self, releaseInfo, progressCb, completionCb)
			self._updater.start()
			return True

		self._status = 'failed'
		return False

	def resetUpdate(self):
		self._status = 'idle'
		self._releases = None
		if self._updater:
			self._updater.stop()
			self._updater = None

	def restartServer(self):
		if platformStr == "linux" or platformStr == "linux2":
			actions = self._settings.get(["system", "actions"])
			for a in actions:
				if a['action'] == 'astrobox-restart':
					#Call to Popen will start the restart command but return inmediately before it completes
					threading.Timer(1.0, subprocess.Popen, [a['command'].split(' ')]).start()
					self._logger.info('Restart command scheduled')

					from astroprint.printer.manager import printerManager
					from astroprint.camera import cameraManager
					from astroprint.network.manager import networkManagerShutdown

					#let's be nice about shutthing things down
					printerManager().disconnect()
					cameraManager().close_camera()
					networkManagerShutdown()

					return True

			return False

		return True

	def sendLogs(self, ticketNo=None, message=None):
		import zipfile

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
		activeLogFiles = ['astrobox.log', 'serial.log', 'electron.log', 'touch.log']

		logsDir = self._settings.getBaseFolder("logs")

		# first delete all old logs
		for f in os.listdir(logsDir):
			path = os.path.join(logsDir, f)

			if os.path.isfile(path) and f not in activeLogFiles:
				os.unlink(path)

		# then truncate the currently used one
		for f in activeLogFiles:
			path = os.path.join(logsDir,f)
			if os.path.isfile(path):
				with open(path, 'w'):
					pass

		return True

	@property
	def systemInfo(self):
		distName, distVersion, id = platform.linux_distribution()
		system, node, release, version, machine, processor = platform.uname()

		outdated = distName == 'debian' and distVersion < '8.0'

		return {
			'dist_name': distName,
			'dist_version': distVersion,
			'system': system,
			'release': release,
			'version': version,
			'machine': machine,
			'processor': processor,
			'outdated': outdated
		}

	def _checkAuth(self):
		if current_user and current_user.is_authenticated and not current_user.is_anonymous:
			privateKey = current_user.privateKey
			publicKey = current_user.publicKey

			if privateKey and publicKey:
				from astroprint.cloud import HMACAuth

				return HMACAuth(publicKey, privateKey)

		return None

	def capabilities(self):
		capabilities = ['remotePrint', 'multiExtruders','allowPrintFile']
		return capabilities
