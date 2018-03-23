__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import subprocess
import os
import threading
import time
import sarge
import pyudev
import fnmatch

from sys import platform

from glob import glob

from astroprint.printer.manager import printerManager

from octoprint.events import eventManager, Events
from octoprint.settings import settings

# singleton
_instance = None

ROOT_MOUNT_POINT = '/media/astrobox'

def externalDriveManager():
	global _instance

	if _instance is None:
		if platform.startswith("linux"):
			_instance = ExternalDriveManager(True)

		elif platform == "darwin":
			_instance = ExternalDriveManager(False)
			logger = logging.getLogger(__name__)
			logger.info('darwin platform is not able to watch external drives plugging...')

	return _instance

#
# Thread to get some plugged usb drive
#
class ExternalDriveManager(threading.Thread):
	def __init__(self, enablingPluggedEvent):
		super(ExternalDriveManager, self).__init__()
		self.daemon = True
		self.stopThread = False
		self.enablingPluggedEvent = enablingPluggedEvent
		self.monitor = None
		self._logger = logging.getLogger(__name__)

	def run(self):
		if self.enablingPluggedEvent:
			context = pyudev.Context()

			#Check the status of the system right now
			for d in context.list_devices(subsystem='block', DEVTYPE='disk'):
				if d.attributes.asbool('removable'):
					#it's removable media, let's find the partitions
					partitions = list(context.list_devices(subsystem='block', DEVTYPE='partition', parent=d))
					if len(partitions) > 0:
						# we only analyze the first one, ignore other partitions
						p = partitions[0]

						#check if the partition is mounted
						mountPoint = self._findMountPoint(p.device_node)
						if mountPoint:
							self._logger.info('Found mounted removable drive (%s) at %s' % (p.device_node, mountPoint))
						else:
							self._logger.info('Mounting inserted removable drive (%s)' % p.device_node)
							self._mountPartition(p.device_node, self._getDeviceMountDirectory(p))

			# Start listening for events
			self.monitor = pyudev.Monitor.from_netlink(context)
			self.monitor.filter_by(subsystem='block')

			for device in iter(self.monitor.poll, None):

				if self.stopThread:
					self.monitor.stop()
					return

				if device.device_type == 'partition':
					if device.action == 'add':
						devName = device.device_node
						self._logger.info('%s pluged in' % devName)
						if self._mountPartition(devName, self._getDeviceMountDirectory(device)):
							eventManager().fire( Events.EXTERNAL_DRIVE_PLUGGED, { "device": devName } )

					if device.action == 'remove':
						devName = device.device_node
						self._logger.info('%s removed' % devName)
						self._umountPartition(self._getDeviceMountDirectory(device))
						eventManager().fire( Events.EXTERNAL_DRIVE_PHISICALLY_REMOVED, { "device": devName })

	def _getDeviceMountDirectory(self, device):
		name = device.get('ID_FS_LABEL')
		uuid = device.get('ID_FS_UUID')
		if name and uuid:
			return os.path.join(ROOT_MOUNT_POINT, uuid, name)
		else:
			return None

	def _findMountPoint(self, devPath):
		with open('/proc/mounts', 'rt') as f:
			for line in f:
				line = line.strip()
				parts = line.split(' ')

				if parts[0] == devPath:
					return parts[1]

		return None

	def _mountPartition(self, partition, directory):
		if directory:
			try:
				if not os.path.exists(directory):
					os.makedirs(directory)

				p = sarge.run('mount %s %s' % (partition, directory), stderr=sarge.Capture())
				if p.returncode != 0:
					returncode = p.returncode
					stderr_text = p.stderr.text
					self._logger.warn("Partition mount failed with return code %i: %s" % (returncode, stderr_text))
					return False

				else:
					self._logger.info("Partition %s mounted on %s" % (partition, directory))
					return True

			except Exception, e:
				self._logger.warn("Mount failed: %s" % e)
				return False
		else:
			return False

	def _umountPartition(self, directory):
		try:
			if os.path.exists(directory):
				p = sarge.run('umount %s' % directory, stderr=sarge.Capture())
				if p.returncode != 0:
					returncode = p.returncode
					stderr_text = p.stderr.text
					self._logger.warn("Partition umount failed with return code %i: %s" % (returncode, stderr_text))
					return False

				else:
					os.rmdir(directory)
					self._logger.info("Partition umounted from %s" % directory)
					return True

			else:
				return True

		except Exception, e:
			self._logger.warn("umount failed: %s" % e)
			return False

	def shutdown(self):
		self._logger.info('Shutting Down ExternalDriveManager')

		if self.enablingPluggedEvent:
			self.stopThread = True

		global _instance
		_instance = None


	def _cleanFileLocation(self, location):
		locationParsed = location.replace('//','/')
		return locationParsed


	def eject(self, mountPath):
		if self._umountPartition(mountPath):
			eventManager().fire( Events.EXTERNAL_DRIVE_EJECTED, { "path": mountPath })
			return {'result': True}
		else:
			return {
				'result': False,
				'error': "Unable to eject"
			}

	def copy(self, src, dst, progressCb, observerId):

			blksize = 1048576 # 1MiB
			try:
					s = open(src, 'rb')
					d = open(dst, 'wb')
			except (KeyboardInterrupt, Exception) as e:
					if 's' in locals():
							s.close()
					if 'd' in locals():
							d.close()
					raise
			try:
					total = float(os.stat(src).st_size)

					while True:
							buf = s.read(blksize)
							bytes_written = d.write(buf)

							progressCb(int((os.stat(dst).st_size / total)*100),dst,observerId)

							if blksize > len(buf) or bytes_written == 0:
									d.write(buf)
									progressCb(100,dst,observerId)
									break

			except (KeyboardInterrupt, Exception) as e:
					s.close()
					d.close()
					raise
			else:
					progressCb(100,dst,observerId)
					s.close()
					d.close()

	def localFileExists(self, filename):
		try:
				s = open(self._cleanFileLocation(self.getBaseFolder('uploads') + '/' + filename), 'rb')
		except Exception as e:
				if 's' in locals():
					s.close()

				return False

		s.close()

		return True

	def _progressCb(self, progress,file,observerId):
		eventManager().fire(
			Events.COPY_TO_HOME_PROGRESS, {
				"type": "progress",
				"file": file,
				"observerId": observerId,
				"progress": progress
			}
		)

	def copyFileToLocal(self, origin, destination, observerId):
		try:
			_origin = self._cleanFileLocation(origin)

			self.copy(_origin,self._cleanFileLocation(destination)+'/'+origin.split('/')[-1:][0],self._progressCb,observerId)

			return True

		except Exception as e:
			self._logger.error("copy print file to local folder failed", exc_info = True)

			return False

	def getRemovableDrives(self):
		return self.getDirContents('%s/*/*' % ROOT_MOUNT_POINT, 'usb')

	def getFileBrowsingExtensions(self):
		return printerManager().fileManager.fileBrowsingExtensions

	def getFolderContents(self, folder):
		try:
			return self.getDirContents(self._cleanFileLocation(folder))

		except Exception as e:
			self._logger.error("exploration folders can not be obtained", exc_info = True)
			return None

	def getBaseFolder(self, key):
		return self._cleanFileLocation(settings().getBaseFolder(key))

	def getDirContents(self, globPattern, icon='folder', extensions=None):
		if extensions is None:
			extensions = self.getFileBrowsingExtensions()

		files = []

		for item in glob(globPattern):
			if os.path.isdir(item):
				files.append({
					'name': item,
					'icon': icon})

			else:
				for ext in extensions:
					if fnmatch.fnmatch(item.lower(), '*' + ext):
						files.append({
							'name': item,
							'icon': ext
						})
						break

		return files

def externalDriveManagerShutdown():
	global _instance

	if _instance:
		_instance.shutdown()
		_instance = None
