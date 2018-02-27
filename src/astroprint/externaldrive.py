__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import shutil

from octoprint.settings import settings

from astroprint.printer.manager import printerManager

def _cleanFileLocation(self, location):
	self._logger.info('location ' + location)
	locationParsed = location.replace('//','/')
	self._logger.info('locationParsed ' + locationParsed)

	return locationParsed


def eject(self, drive):

	args = ['eject', drive]

	try:
		ejectProccess = subprocess.Popen(
			args,
			stdout=subprocess.PIPE
		)

		return {'result': True}

	except Exception, error:

		self._logger.error('Error ejecting drive ' + drive + ': ' + error)

		return {
			'result': False,
			'error': error

		}

def copyFileToLocal(self, origin, destination):
	try:
		shutil.copy2(self._cleanFileLocation(origin),self._cleanFileLocation(destination))
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
		return printerManager().fileManager.getAllStorageLocations()

	except Exception as e:
		self._logger.error("storage folders can not be obtained", exc_info = True)
		return None

def getBaseFolder(self, key):
	return self._cleanFileLocation(settings().getBaseFolder(key))
