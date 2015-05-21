# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import logging
import requests

from Queue import Queue

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
	daemon = True
	activeDownload = False

	_manager = None
	_cancelled = False

	def __init__(self, manager):
		super(DownloadWorker, self).__init__()
		self._manager = manager

	def run(self):
		downloadQueue = self._manager.queue

		while True:
			item = downloadQueue.get()

			printFileId = item['printFileId']
			progressCb = item['progressCb']
			successCb = item['successCb']
			errorCb = item['errorCb']
			destFile = item['destFile']

			self._manager._logger.info('Download started for %s' % printFileId)

			self.activeDownload = printFileId

			#Perform download here
			r = requests.get(item['downloadUrl'], stream=True)

			if r.status_code == 200:
				content_length = float(r.headers['Content-Length']);
				downloaded_size = 0.0

				with open(destFile, 'wb') as fd:
					for chunk in r.iter_content(524288): #0.5 MB
						if self._cancelled:
							break;

						downloaded_size += len(chunk)
						fd.write(chunk)
						progressCb(2 + round((downloaded_size / content_length) * 98.0, 1))

				if self._cancelled:
					self._manager._logger.warn('Download cancelled for %s' % printFileId)
					errorCb(destFile, 'cancelled')

				else:
					fileInfo = {
						'id': printFileId,
						'info': item['printFileInfo']
					}

					successCb(destFile, fileInfo)
					self._manager._logger.info('Download completed for %s' % printFileId)

			else:
				r.close()
				self._manager._logger.error('Download failed for %s' % printFileId)
				errorCb(destFile, 'Unable to download file')

			self.activeDownload = False
			self._cancelled = False
			downloadQueue.task_done()

	def cancel(self):
		if self.activeDownload:
			self._manager._logger.warn('Download cancelled requested for %s' % self.activeDownload)
			self._cancelled = True


class DownloadManager(object):
	_maxWorkers = 3
	_workers = []
	_logger = None

	queue = Queue()

	def __init__(self):
		self._logger = logging.getLogger(__name__)

		for i in range(self._maxWorkers):
			w = DownloadWorker(self)
			self._workers.append( w )
			w.start()

	def startDownload(self, item):
		self.queue.put(item)

	def cancelDownload(self, printFileId):
		for w in self._workers:
			if w.activeDownload == printFileId:
				w.cancel()
				return True

		return False
