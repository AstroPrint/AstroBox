__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import shutil
import subprocess

from octoprint.settings import settings

from astroprint.printer.manager import printerManager

def _cleanFileLocation(location):

	logger = logging.getLogger(__name__)

	logger.info('location ' + location)
	locationParsed = location.replace('//','/')
	logger.info('locationParsed ' + locationParsed)

	return locationParsed


def eject(drive):

	logger = logging.getLogger(__name__)

	args = ['eject', drive]

	try:
		ejectProccess = subprocess.Popen(
			args,
			stdout=subprocess.PIPE
		)

		return {'result': True}

	except Exception, error:

		logger.error('Error ejecting drive %s: %s' %  (drive,str(error)))

		return {
			'result': False,
			'error': str(error)
		}

def copyFileToLocal(origin, destination):
	try:
		shutil.copy2(_cleanFileLocation(origin),_cleanFileLocation(destination))
		return True
	except Exception as e:
		logger = logging.getLogger(__name__)
		logger.error("copy print file to local folder failed", exc_info = True)
		return False


def getFileBrowsingExtensions():
	return printerManager().fileManager.fileBrowsingExtensions


def getFolderExploration(folder):

	try:
		return printerManager().fileManager.getLocationExploration(_cleanFileLocation(folder))

	except Exception as e:
		logger = logging.getLogger(__name__)
		logger.error("exploration folders can not be obtained", exc_info = True)
		return None


def getLocalStorages():

	try:
		return printerManager().fileManager.getLocalStorageLocations()

	except Exception as e:
		logger = logging.getLogger(__name__)
		logger.error("storage folders can not be obtained", exc_info = True)
		return None


def getTopStorages():

	try:
		return printerManager().fileManager.getAllStorageLocations()

	except Exception as e:
		logger = logging.getLogger(__name__)
		logger.error("top storage folders can not be obtained", exc_info = True)
		return None

def getBaseFolder(key):
	return _cleanFileLocation(settings().getBaseFolder(key))
