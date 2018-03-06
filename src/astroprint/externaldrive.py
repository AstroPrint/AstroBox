__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import subprocess
import os

from octoprint.events import eventManager, Events
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

def copy(src, dst, progressCb, observerId):

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

def localFileExists(filename):

	print getBaseFolder('uploads') + '/' + filename

	try:
			s = open(getBaseFolder('uploads') + '/' + filename, 'rb')
	except Exception as e:
			if 's' in locals():
				s.close()

			return False

	s.close()

	return True


def _progressCb(progress,file,observerId):
	eventManager().fire(
		Events.COPY_TO_HOME_PROGRESS, {
			"type": "progress",
			"file": file,
			"observerId": observerId,
			"progress": progress
		}
	)

def copyFileToLocal(origin, destination, observerId):
	try:
		_origin = _cleanFileLocation(origin)
		copy(_origin,_cleanFileLocation(destination)+'/'+origin.split('/')[-1:][0],_progressCb,observerId)

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
