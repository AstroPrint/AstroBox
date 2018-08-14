__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import os
import threading
import sarge
import pyudev
import time

from glob import glob

from octoprint.events import Events

from .base import ExternalDriveBase

#
# Thread to get some plugged usb drive
#
class ExternalDriveManager(ExternalDriveBase):
	ROOT_MOUNT_POINT = '/media/astrobox'

	def __init__(self):
		super(ExternalDriveManager, self).__init__()
		self.stopThread = False
		self._monitor = None
		self._monitorThread = threading.Thread(target=self._monitorLoop)
		self._monitorThread.daemon = True
		self._mountPoints = None
		self._logger = logging.getLogger(__name__)
		self._logger.info('Starting Linux ExternalDriveManager')
		self._monitorThread.start()

	def getRemovableDrives(self):
		return self.getDirContents('%s/*/*' % self.ROOT_MOUNT_POINT, 'usb')

	def _monitorLoop(self):
		context = pyudev.Context()

		#Check the status of the system right now
		# 1. Check if we have any drives connected
		for d in context.list_devices(subsystem='block', DEVTYPE='disk'):
			if d.attributes.asbool('removable'):
				#it's removable media, let's find the partitions
				partitions = list(context.list_devices(subsystem='block', DEVTYPE='partition', parent=d))
				for p in partitions:
					# we only analyze the first one, ignore other partitions
					#p = partitions[0]

					#check if the partition is mounted
					mountPoint = self._findMountPoint(p.device_node)
					if mountPoint:
						self._logger.info('Found mounted removable drive (%s) at %s' % (p.device_node, mountPoint))
					else:
						self._logger.info('Mounting inserted removable drive (%s)' % p.device_node)
						self._mountPartition(p.device_node, self._getDeviceMountDirectory(p))

		# 2. Check if there are left over directories with no drives mounted
		for f in glob('%s/*/*' % self.ROOT_MOUNT_POINT):
			if os.path.isdir(f) and not os.listdir(f):
				#empty directory found, let's see if it's mounted
				if not self._isMounted(f):
					#Not mounted and empty, delete directory.
					os.rmdir(f) #main dir
					os.rmdir('/'.join(f.split('/')[:-1])) #uuid dir

		self._mountPoints = None # We reset here since we don't need it anymore, it will be re-created on shutdown

		# Start listening for events
		self._monitor = pyudev.Monitor.from_netlink(context)
		self._monitor.filter_by(subsystem='block')

		for device in iter(self._monitor.poll, None):

			if self.stopThread:
				self._monitor.stop()
				return

			if device.device_type == 'partition':
				if device.action == 'add':
					devName = device.device_node
					self._logger.info('%s pluged in' % devName)
					mountPath = self._getDeviceMountDirectory(device)
					if self._mountPartition(devName, mountPath):
						self._eventManager.fire( Events.EXTERNAL_DRIVE_MOUNTED, {
							"mount_path": mountPath,
							"device_node": devName
						})

				if device.action == 'remove':
					devName = device.device_node
					mountPath = self._getDeviceMountDirectory(device)
					self._logger.info('%s removed' % devName)
					if self._umountPartition(self._getDeviceMountDirectory(device)):
						self._eventManager.fire( Events.EXTERNAL_DRIVE_PHISICALLY_REMOVED, {
							"device_node": devName,
							"mount_path": mountPath,
						})

	def _getDeviceMountDirectory(self, device):
		name = device.get('ID_FS_LABEL', 'NO NAME')
		uuid = device.get('ID_FS_UUID')
		if name and uuid:
			return os.path.join(self.ROOT_MOUNT_POINT, uuid, name)
		else:
			return None

	def _loadMountPoints(self):
		self._mountPoints = {}
		with open('/proc/mounts', 'rt') as f:
			for line in f:
				line = line.strip()
				parts = line.split(' ')

				self._mountPoints[parts[0]] = parts[1]

	def _findMountPoint(self, devPath):
		if self._mountPoints is None:
			self._loadMountPoints()

		return self._mountPoints.get(devPath)

	def _isMounted(self, dirPath):
		if self._mountPoints is None:
			self._loadMountPoints()

		for dev, path in self._mountPoints.iteritems():
			if path == dirPath:
				return True

		return False

	def _mountPartition(self, partition, directory):
		if directory:
			try:
				if not os.path.exists(directory):
					os.makedirs(directory)

				p = sarge.run("mount -o iocharset=utf8 %s '%s'" % (partition, directory), stderr=sarge.Capture())
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
		if directory:
			try:
				if os.path.exists(directory):
					p = sarge.run("umount '%s'" % directory, stderr=sarge.Capture())
					if p.returncode != 0:
						returncode = p.returncode
						stderr_text = p.stderr.text
						self._logger.warn("Partition umount failed with return code %i: %s" % (returncode, stderr_text))
						return False

					else:
						os.rmdir(directory)
						os.rmdir('/'.join(directory.split('/')[:-1])) #uuid dir
						self._logger.info("Partition umounted from %s" % directory)
						return True

				else:
					return True

			except Exception, e:
				self._logger.warn("umount failed: %s" % e)
				return False

		else:
			return False

	def shutdown(self):
		self._logger.info('Shutting Down Linux ExternalDriveManager')

		#Unmount mounted drives
		for d in glob('%s/*/*' % self.ROOT_MOUNT_POINT):
			if self._isMounted(d):
				self._umountPartition(d)

		self.stopThread = True

	def eject(self, mountPath):

		retries = 5
		timeout = 3

		ejected = False

		for i in (0,retries):
			if self._umountPartition(mountPath):
				ejected = True
			else:
				time.sleep(timeout)

		if ejected:
			self._eventManager.fire( Events.EXTERNAL_DRIVE_EJECTED, {
				"mount_path": mountPath
			})
			return {'result': True}

		return {
			'result': False,
			'error': "Unable to eject"
		}
