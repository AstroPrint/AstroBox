# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService

from octoprint.settings import settings
import octoprint.util as util

from astroprint.printer.manager import printerManager
from astroprint.printfiles import FileDestinations

class FilesService(PluginService):
	_validEvents = [
		#watch if a file where added
		#'file_added',
		#watch if a file where deleted
		'file_deleted'
	]

	def __init__(self):
		super(FilesService, self).__init__()

	def getLocalFiles(self, sendResponse):
		print 'getLocalFiles'
		try:
			try:
				files = self._getLocalFileList(FileDestinations.LOCAL)
			except:
				pass

			try:
				files.extend(self._getLocalFileList(FileDestinations.SDCARD))
			except:
				pass
			sendResponse( { 'files': files, 'free': util.getFreeBytes(settings().getBaseFolder("uploads")) })

		except Exception as e:
			self._logger.error("files can not be obtained", exc_info = True)
			sendResponse('no_files_obtained',True)

	def _getLocalFileList(self, data):

		origin = data

		if origin == FileDestinations.SDCARD:
			sdFileList = printerManager().getSdFiles()

			files = []
			if sdFileList is not None:
				for sdFile, sdSize in sdFileList:
					file = {
						"name": sdFile,
						"origin": FileDestinations.SDCARD,
						#"refs": {
						#	"resource": url_for(".readPrintFile", target=FileDestinations.SDCARD, filename=sdFile, _external=True)
						#}
					}
					if sdSize is not None:
						file.update({"size": sdSize})
					files.append(file)
		else:
			files = printerManager().fileManager.getAllFileData()
			'''for file in files:
				file.update({
					"refs": {
						"resource": url_for(".readPrintFile", target=FileDestinations.LOCAL, filename=file["name"], _external=True),
						"download": url_for("index", _external=True) + "downloads/files/" + FileDestinations.LOCAL + "/" + file["name"]
					}
				})'''
		return files

	def _verifyFileExists(self,origin, filename):
		if origin == FileDestinations.SDCARD:
			availableFiles = map(lambda x: x[0], printerManager().getSdFiles())
		else:
			availableFiles = printerManager().fileManager.getAllFilenames()

		return filename in availableFiles

	def printFile(self, data, sendResponse):
		print 'printFile'
		fileDestination = fileName = None

		if 'location' in data:
			fileDestination = data['location']

		if 'fileName' in data:
			fileName = data['fileName']

		if not fileDestination in [FileDestinations.LOCAL, FileDestinations.SDCARD]:
			self._logger.error('Unknown file location', exc_info = True)
			sendResponse('unknown_file_location',True)

		if not fileName or not self._verifyFileExists(fileDestination, fileName):
			self._logger.error('File not found', exc_info = True)
			sendResponse('file_not_found',True)

		# valid file commands, dict mapping command name to mandatory parameters
		valid_commands = {
			"select": []
		}

		printer = printerManager()

		# selects/loads a file
		printAfterLoading = False
		if "print" in data.keys() and data["print"]:
			if not printer.isOperational():
				#We try at least once
				printer.connect()

				start = time.time()
				connect_timeout = 5 #5 secs

				while not printer.isOperational() and not printer.isClosedOrError() and time.time() - start < connect_timeout:
					time.sleep(1)

				if not printer.isOperational():
					self._logger.error("The printer is not responding, can't start printing", exc_info = True)
					sendResponse('printer_not_responding',True)
					return

			printAfterLoading = True

		sd = False
		if fileDestination == FileDestinations.SDCARD:
			filenameToSelect = fileName
			sd = True
		else:
			filenameToSelect = printer.fileManager.getAbsolutePath(fileName)

		startPrintingStatus = printer.selectFile(filenameToSelect, sd, printAfterLoading)

		if startPrintingStatus:
			sendResponse({'success':'no error'})
		else:
			sendResponse('printer_not_responding',True)

	def deletePrintFile(self, data, sendResponse):

		fileDestination = fileName = None

		if 'location' in data:
			fileDestination = data['location']

		if 'fileName' in data:
			fileName = data['fileName']

		if not fileDestination in [FileDestinations.LOCAL, FileDestinations.SDCARD]:
			self._logger.error("Unknown file location", exc_info = True)
			sendResponse('unknown_file_location',True)
			return

		if not fileName or not self._verifyFileExists(fileDestination, fileName):
			self._logger.error("File not found", exc_info = True)
			sendResponse('file_not_found',True)
			return

		sd = fileDestination == FileDestinations.SDCARD

		printer = printerManager()

		currentJob = printer.getCurrentJob()
		currentFilename = None
		currentSd = None
		if currentJob is not None and "fileName" in currentJob.keys() and "sd" in currentJob.keys():
			currentFilename = currentJob["fileName"]
			currentSd = currentJob["sd"]

		# prohibit deleting the file that is currently being printed
		if currentFilename == fileName and currentSd == sd and (printer.isPrinting() or printer.isPaused()):
			sendResponse("Trying to delete file that is currently being printed: %s" % fileName,true)

		# deselect the file if it's currently selected
		if currentFilename is not None and fileName == currentFilename:
			printer.unselectFile()

		# delete it
		if sd:
			printer.deleteSdFile(fileName)
		else:
			printer.fileManager.removeFile(fileName)

		self.publishEvent('file_deleted','deleted')
		sendResponse({'success':'no error'})
