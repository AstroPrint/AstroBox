__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import subprocess
import os
import threading
import time

from astroprint.printer.manager import printerManager

from octoprint.events import eventManager, Events
from octoprint.settings import settings

class FilesSystemReadyWorker(threading.Thread):

	def __init__(self, device):
		super(FilesSystemReadyWorker,self).__init__()
		self.daemon = True

		self.device = device

		path = settings().getBaseFolder('storageLocation').replace('//','/')

		self.previousStorages = printerManager().fileManager.getLocalStorageLocations()


	def run(self):
		newStorageFound = False

		while not newStorageFound:
			time.sleep(0.5)
			currentStorages = printerManager().fileManager.getLocalStorageLocations()
			newStorageFound = (self.previousStorages != printerManager().fileManager.getLocalStorageLocations())

		eventManager().fire(
			Events.EXTERNAL_DRIVE_PLUGGED, {
				"device": self.device.sys_name
			}
		)

		return


from sys import platform

# singleton
_instance = None

def externalDriveManager():
	global _instance

	if _instance is None:
		if platform == "linux" or platform == "linux2":
			_instance = ExternalDriveManager(True)

		elif platform == "darwin":
			_instance = ExternalDriveManager(False)
			logger = logging.getLogger(__name__)
			logger.info('darwin platform is not able to watch external drives plugging...')

	return _instance


import pyudev

#
# Thread to get some plugged usb drive
#
class ExternalDriveManager(threading.Thread):
	def __init__(self, enablingPluggedEvent):
		super(ExternalDriveManager, self).__init__()
		self.daemon = True

		self.stopThread = False

		self.enablingPluggedEvent = enablingPluggedEvent

		if enablingPluggedEvent:
			self.context = pyudev.Context()
			self.monitor = pyudev.Monitor.from_netlink(self.context)
			self.monitor.filter_by(subsystem='usb')

		self._logger = logging.getLogger(__name__)


	def run(self):
		if self.enablingPluggedEvent:
			for device in iter(self.monitor.poll, None):
				if self.stopThread:
					self.monitor.stop()
					self.join()
					return

				if device.device_type == 'usb_device':

					print device.action

					if device.action == 'add':

						self._logger.info('{} connected'.format(device))

						FilesSystemReadyWorker(device).start()

					if device.action == 'remove':

						self._logger.info('{} disconnected'.format(device))



	def shutdown(self):
		self._logger.info('Shutting Down ExternalDriveManager')

		if self.enablingPluggedEvent:
			self.stopThread = True

		global _instance
		_instance = None


	def _cleanFileLocation(self, location):

		locationParsed = location.replace('//','/')

		return locationParsed


	def eject(self, drive):

		args = ['eject', settings().getBaseFolder('storageLocation').replace('//','/') + drive]

		try:
			ejectProccess = subprocess.Popen(
				args,
				stdout=subprocess.PIPE
			)

			return {'result': True}

		except Exception, error:

			self._logger.error('Error ejecting drive %s: %s' %  (drive,str(error)))

			return {
				'result': False,
				'error': str(error)
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

		print self.getBaseFolder('uploads') + '/' + filename

		try:
				s = open(self._cleanFileLocation(self.getBaseFolder('uploads') + '/' + filename), 'rb')
		except Exception as e:
				print 'exception'
				print e
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


	def getFileBrowsingExtensions(self):
		return printerManager().fileManager.fileBrowsingExtensions


	def getFolderExploration(self, folder):

		try:
			return printerManager().fileManager.getLocationExploration(self._cleanFileLocation(folder))

		except Exception as e:
			self._logger.error("exploration folders can not be obtained", exc_info = True)
			return None


	def getLocalStorages(self):

		try:
			return printerManager().fileManager.getLocalStorageLocations()

		except Exception as e:
			self._logger.error("storage folders can not be obtained", exc_info = True)
			return None


	def getTopStorages(self):

		try:
			return printerManager().fileManager.getAllStorageLocations()

		except Exception as e:
			self._logger.error("top storage folders can not be obtained", exc_info = True)
			return None

	def getBaseFolder(self, key):
		return self._cleanFileLocation(settings().getBaseFolder(key))

def externalDriveManagerShutdown():
	global _instance

	if _instance:
		_instance.shutdown()
		_instance = None
