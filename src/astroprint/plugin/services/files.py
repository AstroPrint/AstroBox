# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import os
import time
from . import PluginService

from flask_login import current_user
from flask import jsonify

import octoprint.util as util
from octoprint.events import eventManager, Events
from octoprint.settings import settings
from octoprint.server import restricted_access

from astroprint.cloud import astroprintCloud
from astroprint.printer.manager import printerManager
from astroprint.printfiles import FileDestinations
from astroprint.printfiles.downloadmanager import downloadManager

class FilesService(PluginService):
	_validEvents = [
		#watch if a file where added
		#'file_added',
		#BROWSER -> PLUGIN
		#watch if a file where deleted
		'file_deleted',
		#watch if a file were be downloaded successfully
		'cloud_download_success',
		################
		#PLUGIN -> BROWSER + PLUGIN
		#watch downloading progress of a print file
		'progress_download_printfile',
		#watch if a print file were downloaded: successfully or failed(error or cancelled)
		'f¡nished_download_printfile'

	]

	def __init__(self):
		super(FilesService, self).__init__()

		#files managing
		self._eventManager.subscribe(Events.FILE_DELETED, self._onFileDeleted)
		self._eventManager.subscribe(Events.CLOUD_DOWNLOAD, self._onCloudDownloadStateChanged)

	def getLocalFiles(self, sendResponse):
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

		printer = printerManager()

		# selects/loads a file
		printAfterLoading = False
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

		eventManager().fire(Events.FILE_DELETED, {"filename": fileName})

		self.publishEvent('file_deleted','deleted')

		sendResponse({'success':'no error'})


	def downloadPrintFile(self,printFileId,sendResponse):
		em = eventManager()

		def progressCb(progress):
			self.publishEvent('progress_download_printfile', {
				"type": "progress",
				"id": printFileId,
				"progress": progress
			})

		def successCb(destFile, fileInfo):
			if fileInfo is True:
				#This means the files was already on the device

				data = {
					"type": "success",
					"id": printFileId,
					"filename": printerManager().fileManager._getBasicFilename(destFile)
				}

				self.publishEvent('f¡nished_download_printfile',data)
				em.fire(Events.CLOUD_DOWNLOAD,data)

			else:
				data = {
					"type": "success",
					"id": printFileId,
					"filename": printerManager().fileManager._getBasicFilename(destFile),
					"info": fileInfo["info"],
					"printer": fileInfo["printer"],
					"material": fileInfo["material"],
					"quality": fileInfo["quality"],
					"image": fileInfo["image"],
					"created": fileInfo["created"]
				}

				self.publishEvent('f¡nished_download_printfile',data)

		def errorCb(destFile, error):
			if error == 'cancelled':
				data = {
					"type": "cancelled",
					"id": printFileId
				}

				self.publishEvent('f¡nished_download_printfile',data)
				em.fire(Events.CLOUD_DOWNLOAD,data)

			else:
				data = {
					"type": "error",
					"id": printFileId,
					"reason": error
				}

				em.fire(Events.CLOUD_DOWNLOAD,data)
				self.publishEvent('f¡nished_download_printfile',data)

			if destFile and os.path.exists(destFile):
				os.remove(destFile)

		if astroprintCloud().download_print_file(printFileId, progressCb, successCb, errorCb):
			sendResponse({'success':'no error'})
			return

		sendResponse('error',True)
		return

	def cancelDownloadPrintFile(self, printFileId, sendResponse):

		if downloadManager().cancelDownload(printFileId):
			sendResponse({'success':'no error'})
		else:
			sendResponse('cancel_error',True)


	#EVENTS

	def _onFileDeleted(self,event,data):
		self.publishEvent('file_deleted',data['filename'])

	def _onCloudDownloadStateChanged(self,event,data):
		if data['type'] == 'success':
			self.publishEvent('cloud_download_success',data)
		#else TODO
