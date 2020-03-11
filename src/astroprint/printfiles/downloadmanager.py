# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2016-2019 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import threading
import logging
import requests

from Queue import Queue
from astroprint.printer.manager import printerManager
from octoprint.events import eventManager, Events
from astroprint.printfiles import FileDestinations

# singleton
_instance = None

def downloadManager():
	global _instance
	if _instance is None:
		_instance = DownloadManager()
	return _instance

# download item is:

# downloadUrl 	: url to of the file to download
# destFile		: destination file
# printFileId 	: Id of the print file to be downloaded,
# printFileInfo : Cloud info of the print file to be downloaded,
# progressCb 	: callback to report progress
# successCb 	: callback to report success
# errorCb 		: callback to report errors

class DownloadWorker(threading.Thread):
	def __init__(self, manager):
		self._daemon = True
		self._manager = manager
		self._activeRequest = None
		self._canceled = False
		self.activeDownload = False

		super(DownloadWorker, self).__init__()

	def run(self):
		downloadQueue = self._manager.queue

		while True:
			item = downloadQueue.get()
			if item == 'shutdown':
				return

			printFileId = item['printFileId']
			printFileName = item['printFileName']
			progressCb = item['progressCb']
			successCb = item['successCb']
			errorCb = item['errorCb']
			destFile = item['destFile']
			printer = None
			material = None
			quality = None
			image = None
			created = None
			retries = 3

			if "printer" in item:
				printer = item['printer']
			if "material" in item:
				material = item['material']
			if "quality" in item:
				quality = item['quality']
			if "image" in item:
				image = item['image']
			if "created" in item:
				created = item['created']

			self._manager._logger.info('Download started for %s' % printFileId)

			self.activeDownload = printFileId
			self._canceled = False

			while retries > 0:
				try:
					#Perform download here
					r = requests.get(item['downloadUrl'], stream= True, timeout= (10.0, 5.0)) #(connect timeout, read timeout)
					self._activeRequest = r

					if r.status_code == 200:
						content_length = float(r.headers['Content-Length'])
						downloaded_size = 0.0

						if not self._canceled:
							with open(destFile, 'wb') as fd:
								for chunk in r.iter_content(100000): #download 100kb at a time
									if self._canceled: #check right after reading
										break

									downloaded_size += len(chunk)
									fd.write(chunk)
									progressCb(2 + round((downloaded_size / content_length) * 98.0, 1))

									if self._canceled: #check again before going to read next chunk
										break

						retries = 0 #No more retries after this
						if not self._canceled:
							self._manager._logger.info('Download completed for %s' % printFileId)

							if item['printFileInfo'] is None:
								printerManager().fileManager._metadataAnalyzer.addFileToQueue(destFile)

							fileInfo = {
								'id': printFileId,
								'printFileName': printFileName,
								'info': item['printFileInfo'],
								'printer': printer,
								'material': material,
								'quality': quality,
								'image': image,
								'created': created
							}

							em = eventManager()

							if printerManager().fileManager.saveCloudPrintFile(destFile, fileInfo, FileDestinations.LOCAL):
								em.fire(
									Events.CLOUD_DOWNLOAD, {
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
								)

								successCb(destFile, fileInfo)

							else:
								errorCb(destFile, "Couldn't save the file")

					elif r.status_code in [502, 503, 500]:
						self._manager._logger.warn('Download failed for %s with %d. Retrying...' % (printFileId, r.status_code))
						retries -= 1 #This error can be retried

					else:
						self._manager._logger.error('Download failed for %s with %d' % (printFileId, r.status_code))
						errorCb(destFile, 'The device is unable to download the print file')
						retries = 0 #No more retries after this

				except requests.exceptions.ConnectTimeout as e:
					self._manager._logger.warn('Connection timeout for %s. Retrying...' % printFileId)
					retries -= 1 #This error can be retried

				except requests.exceptions.ReadTimeout as e:
					self._manager._logger.warn('Read timeout for %s' % printFileId)
					not self._canceled and errorCb(destFile, 'Network erros while downloading the print file')
					retries = 0 #No more retries after this

				except requests.exceptions.RequestException as e:
					self._manager._logger.error('Download connection exception for %s: %s' % (printFileId, e), exc_info=True)
					not self._canceled and errorCb(destFile, 'Connection Error while downloading the print file')
					retries = 0 #No more retries after this

				except Exception as e:
					retries = 0 #No more retries after this
					if "'NoneType' object has no attribute 'recv'" != str(e):
						# Ignore above error. It's due to a problem in the underlying library when calling r.close in the cancel routine
						self._manager._logger.error('Download exception for %s: %s' % (printFileId, e), exc_info=True)
						not self._canceled and errorCb(destFile, 'The device is unable to download the print file')
						r.close()

				finally:
					if self._canceled:
						retries = 0 #No more retries after this
						self._manager._logger.warn('Download canceled for %s' % printFileId)
						errorCb(destFile, 'cancelled')

			self.activeDownload = False
			self._activeRequest = None
			downloadQueue.task_done()

	def cancel(self):
		if self.activeDownload and not self._canceled:
			if self._activeRequest:
				self._activeRequest.close()

			self._manager._logger.warn('Download canceled requested for %s' % self.activeDownload)
			self._canceled = True


class DownloadManager(object):
	_maxWorkers = 3

	def __init__(self):
		self._logger = logging.getLogger(__name__)
		self.queue = Queue()

		self._workers = []
		for i in range(self._maxWorkers):
			w = DownloadWorker(self)
			self._workers.append( w )
			w.start()

	def isDownloading(self, printFileId):
		for w in self._workers:
			if w.activeDownload == printFileId:
				return True

		return False

	def startDownload(self, item):
		self.queue.put(item)

	def cancelDownload(self, printFileId):
		for w in self._workers:
			if w.activeDownload == printFileId:
				w.cancel()
				return True

		return False

	def shutdown(self):
		self._logger.info('Shutting down Download Manager...')
		for w in self._workers:
			self.queue.put('shutdown')
			if w.activeDownload:
				w.cancel()
