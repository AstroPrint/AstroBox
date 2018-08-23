__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2018 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os

from glob import glob

from werkzeug.utils import secure_filename

from octoprint.events import eventManager, Events
from octoprint.settings import settings


from astroprint.printer.manager import printerManager

class ExternalDriveBase(object):
	def __init__(self):
		self._eventManager = eventManager()

	def getDirContents(self, globPattern, icon='folder', extensions=None):
		if extensions is None:
			extensions = self.getFileBrowsingExtensions()

		files = []
		folders = []

		for item in glob(globPattern):
			if os.path.isdir(item):
				folders.append({
					'name': item,
					'icon': icon})

			else:
				f, ext = os.path.splitext(item)
				ext = ext[1:]

				if ext in extensions:
					files.append({
						"name": item,
						"size": os.stat(item).st_size,
						"icon": ext
					})

		return sorted(folders, key=lambda f: f['name'].lower()) + sorted(files, key=lambda f: f['name'].lower())

	def getFolderContents(self, folder):
		try:
			return self.getDirContents(self._cleanFileLocation(folder))

		except Exception as e:
			self._logger.error("Error getting folder contents", exc_info = True)
			return None

	def getBaseFolder(self, key):
		return self._cleanFileLocation(settings().getBaseFolder(key))

	def getFileBrowsingExtensions(self):
		return printerManager().fileManager.SUPPORTED_EXTENSIONS

	def localFileExists(self, filename):
		try:
			filename = secure_filename(filename)
			s = open(self._cleanFileLocation(self.getBaseFolder('uploads') + '/' + filename), 'rb')
		except Exception as e:
			return False

		s.close()
		return True

	def copy(self, src, dst, progressCb, observerId):
		blksize = 1048576 # 1MiB
		s = None
		d = None

		try:
			s = open(src, 'rb')
			d = open(dst, 'wb')

			sizeWritten = 0.0
			total = float( os.stat(src).st_size )

			while sizeWritten < total:
				buf = s.read(blksize)
				d.write(buf)

				sizeWritten += len(buf)

				progressCb((sizeWritten / total)*100, dst, observerId)

			printerManager().fileManager._metadataAnalyzer.addFileToQueue(dst)
			progressCb(100.0,dst,observerId)

		except (KeyboardInterrupt, Exception) as e:
			raise

		finally:
			if s:
				s.close()

			if d:
				d.close()

	def copyFileToLocal(self, origin, destination, observerId):
		try:
			secureFilename = secure_filename(origin.split('/')[-1:][0])
			self.copy(
				self._cleanFileLocation(origin),
				self._cleanFileLocation(destination) + '/' + secureFilename,
				self._progressCb,
				observerId
			)

			return secureFilename

		except Exception as e:
			self._logger.error("copy print file to local folder failed", exc_info = True)

			return False

	def _progressCb(self, progress,file,observerId):
		self._eventManager.fire(
			Events.COPY_TO_HOME_PROGRESS, {
				"type": "progress",
				"file": file,
				"observerId": observerId,
				"progress": progress
			}
		)

	def _cleanFileLocation(self, location):
		locationParsed = location.replace('//','/')
		return locationParsed
