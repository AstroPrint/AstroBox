__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import os

from astroprint.printer.manager import printerManager

from octoprint.settings import settings

from .base import ExternalDriveBase

#
# Thread to get some plugged usb drive
#
class ExternalDriveManager(ExternalDriveBase):
	ROOT_MOUNT_POINT = '/Volumes'

	def __init__(self):
		super(ExternalDriveManager, self).__init__()
		self._logger = logging.getLogger(__name__)
		self._logger.info('Starting Mac ExternalDriveManager')

	def shutdown(self):
		self._logger.info('Shutting Down Mac ExternalDriveManager')

	def eject(self, mountPath):
		pass

	def getRemovableDrives(self):
		return self.getDirContents('%s/*' % self.ROOT_MOUNT_POINT, 'usb')
