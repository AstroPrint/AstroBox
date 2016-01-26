import os
import logging
import threading
import weakref
import base64

from octoprint.events import eventManager, Events

from astroprint.camera import cameraManager
from astroprint.cloud import astroprintCloud
from astroprint.printer.manager import printerManager
from astroprint.printerprofile import printerProfileManager

class RequestHandler(object):
	def __init__(self, printerListener):
		self._logger = logging.getLogger(__name__)
		self._weakPrinterListener = weakref.ref(printerListener)

	def initial_state(self, data):
		printer = printerManager()

		return {
			'printing': printer.isPrinting(),
			'operational': printer.isOperational(),
			'paused': printer.isPaused(),
			'camera': printer.isCameraConnected(),
			'printCapture': cameraManager().timelapseInfo,
			'profile': printerProfileManager().data,
			'remotePrint': True
		}

	def job_info(self, data):
		return printerManager()._stateMonitor._jobData

	def printerCommand(self, data):
		return self._handleCommandGroup(PrinterCommandHandler, data)

	def cameraCommand(self, data):
		return self._handleCommandGroup(CameraCommandHandler, data)

	def printCapture(self, data):
		freq = data['freq']
		if freq:
			cm = cameraManager()

			if cm.timelapseInfo:
				if not cm.update_timelapse(freq):
					return {
						'error': True,
						'message': 'Error updating the print capture'
					}

			else:
				if not cm.start_timelapse(freq):
					return {
						'error': True,
						'message': 'Error creating the print capture'
					}

		else:
			return {
				'error': True,
				'message': 'Frequency required'
			}

	def signoff(self, data):
		self._logger.info('Remote signoff requested.')
		threading.Timer(1, astroprintCloud().remove_logged_user).start()

	def print_file(self, data):
		from astroprint.printfiles import FileDestinations

		print_file_id = data['printFileId']

		printer = printerManager()
		em = eventManager()

		def progressCb(progress):
			em.fire(
				Events.CLOUD_DOWNLOAD, {
					"type": "progress",
					"id": print_file_id,
					"progress": progress
				}
			)

		def successCb(destFile, fileInfo):
			if fileInfo is not True:
				if printer.fileManager.saveCloudPrintFile(destFile, fileInfo, FileDestinations.LOCAL):
					em.fire(
						Events.CLOUD_DOWNLOAD, {
							"type": "success",
							"id": print_file_id,
							"filename": printer.fileManager._getBasicFilename(destFile),
							"info": fileInfo["info"]
						}
					)

				else:
					errorCb(destFile, "Couldn't save the file")
					return

			abosluteFilename = printer.fileManager.getAbsolutePath(destFile)
			if printer.selectFile(abosluteFilename, False, True):
				pl = self._weakPrinterListener()

				if pl:
					pl._sendUpdate('print_file_download', {
						'id': print_file_id,
						'progress': 100,
						'selected': True
					})

			else:
				pl = self._weakPrinterListener()

				if pl:
					pl._sendUpdate('print_file_download', {
						'id': print_file_id,
						'progress': 100,
						'error': True,
						'message': 'Unable to start printing',
						'selected': False
					})

		def errorCb(destFile, error):
			if error == 'cancelled':
				em.fire(
						Events.CLOUD_DOWNLOAD,
						{
							"type": "cancelled",
							"id": print_file_id
						}
					)
			else:
				em.fire(
					Events.CLOUD_DOWNLOAD,
					{
						"type": "error",
						"id": print_file_id,
						"reason": error
					}
				)

			if destFile and os.path.exists(destFile):
				os.remove(destFile)

		if not astroprintCloud().download_print_file(print_file_id, progressCb, successCb, errorCb):
			return {
				'error': True,
				'message': 'Unable to start download process'
			}

	def cancel_download(self, data):
		from astroprint.printfiles.downloadmanager import downloadManager

		print_file_id = data['printFileId']

		if not downloadManager().cancelDownload(print_file_id):
			return {
				'error': True,
				'message': 'Unable to cancel download'
			}

	def _handleCommandGroup(self, handlerClass, data):
		handler = handlerClass()

		command = data['command']
		options = data['options']

		method  = getattr(handler, command)
		if method:
			return method(options)

		else:
			return {
				'error': True,
				'message': '%s::%s is not supported' % (handlerClass, command)
			}

# Printer Command Group Handler

class PrinterCommandHandler(object):
	def pause(self, data):
		printerManager().togglePausePrint()

	def resume(self, data):
		self.pause()

	def cancel(self, data):
		printerManager().cancelPrint()

	def photo(self, data):
		return {
			'success': True,
			'image_data': base64.b64encode(cameraManager().get_pic())
		}

# Camera Command Group Handler

class CameraCommandHandler(object):
	def start_video_stream(self, data):
		cameraManager().start_video_stream()

	def stop_video_stream(self, data):
		cameraManager().stop_video_stream()
