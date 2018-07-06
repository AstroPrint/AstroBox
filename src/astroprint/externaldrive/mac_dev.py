__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging

from astroprint.printer.manager import printerManager

from octoprint.settings import settings

#
# Thread to get some plugged usb drive
#
class ExternalDriveManager(object):
	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self._logger.info('Starting Mac ExternalDriveManager')

	def shutdown(self):
		self._logger.info('Shutting Down Mac ExternalDriveManager')

	def eject(self, mountPath):
		pass

	def copy(self, src, dst, progressCb, observerId):
		pass

	def localFileExists(self, filename):
		pass

	def copyFileToLocal(self, origin, destination, observerId):
		pass

	def getRemovableDrives(self):
		return [
			{"name": 'Test_1', "icon": "usb"},
			{"name": 'Test_2', "icon": "usb"}
		]

	def getFileBrowsingExtensions(self):
		return printerManager().fileManager.SUPPORTED_EXTENSIONS

	def getFolderContents(self, folder):
		if folder.startswith('/Test_1/'):
			return [
				{"name": 'Test_1_1', "icon": "folder"},
				{"name": 'This is a very long gcode file.gcode', "icon": "gcode"}
			]

		elif folder.startswith('/Test_2/'):
			return [
				{"name": 'Print file.gcode', "icon": "gcode"}
			]

	def getBaseFolder(self, key):
		return settings().getBaseFolder(key)
