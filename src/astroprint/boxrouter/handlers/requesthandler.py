# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import os
import logging
import threading
import weakref
import base64
import json

from octoprint.events import eventManager, Events
from octoprint.settings import settings

from astroprint.camera import cameraManager
from astroprint.cloud import astroprintCloud
from astroprint.printer.manager import printerManager
from astroprint.printerprofile import printerProfileManager
from astroprint.webrtc import webRtcManager
from astroprint.software import softwareManager as swManager

class RequestHandler(object):
	def __init__(self, wsClient):
		self._logger = logging.getLogger(__name__)
		self._wsClient = wsClient

	def initial_state(self, data, clientId, done):
		printer = printerManager()
		cm = cameraManager()
		softwareManager = swManager()

		state = {
			'printing': printer.isPrinting(),
			'heatingUp': printer.isHeatingUp(),
			'operational': printer.isOperational(),
			'paused': printer.isPaused(),
			'camera': printer.isCameraConnected(),
			'printCapture': cm.timelapseInfo,
			'profile': printerProfileManager().data,
			'remotePrint': True,
			'capabilities': softwareManager.capabilities() + cm.capabilities,
			'tool': printer.getSelectedTool() if printer.isOperational() else None,
			'printSpeed': printer.getPrintingSpeed(),
			'printFlow': printer.getPrintingFlow()
		}

		if state['printing'] or state['paused']:
			#Let's add info about the ongoing print job
			state['job'] = printer._stateMonitor._jobData
			state['progress'] = printer._stateMonitor._progress

		done(state)

	def job_info(self, data, clientId, done):
		done(printerManager()._stateMonitor._jobData)

	def printerCommand(self, data, clientId, done):
		self._handleCommandGroup(PrinterCommandHandler, data, clientId, done)

	def cameraCommand(self, data, clientId, done):
		self._handleCommandGroup(CameraCommandHandler, data, clientId, done)

	def p2pCommand(self, data, clientId, done):
		self._handleCommandGroup(P2PCommandHandler, data, clientId, done)

	def printCapture(self, data, clientId, done):
		freq = data['freq']
		if freq:
			cm = cameraManager()

			if cm.timelapseInfo:
				if not cm.update_timelapse(freq):
					done({
						'error': True,
						'message': 'Error updating the print capture'
					})
					return

			else:
				r = cm.start_timelapse(freq)
				if r != 'success':
					done({
						'error': True,
						'message': 'Error creating the print capture: %s' % r
					})
					return
		else:
			done({
				'error': True,
				'message': 'Frequency required'
			})
			return

		done(None)

	def signoff(self, data, clientId, done):
		self._logger.info('Remote signoff requested.')
		threading.Timer(1, astroprintCloud().remove_logged_user).start()
		done(None)

	def print_file(self, data, clientId, done):
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
			abosluteFilename = printer.fileManager.getAbsolutePath(destFile)
			if printer.selectFile(abosluteFilename, False, True):
				eventData = {
					'id': print_file_id,
					'progress': 100,
					'selected': True
				}

			else:
				eventData = {
					'id': print_file_id,
					'progress': 100,
					'error': True,
					'message': 'Unable to start printing',
					'selected': False
				}

			self._wsClient.send(json.dumps({
				'type': 'send_event',
				'data': {
					'eventType': 'print_file_download',
					'eventData': eventData
				}
			}))

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
			done({
				'error': True,
				'message': 'Unable to start download process'
			})
			return

		done(None)

	def cancel_download(self, data, clientId, done):
		from astroprint.printfiles.downloadmanager import downloadManager

		print_file_id = data['printFileId']

		if not downloadManager().cancelDownload(print_file_id):
			done({
				'error': True,
				'message': 'Unable to cancel download'
			})
			return

		done(None)

	def _handleCommandGroup(self, handlerClass, data, clientId, done):
		handler = handlerClass()

		command = data['command']
		options = data['options']

		method  = getattr(handler, command, None)
		if method:
			#return method(options, clientId)
			method(options, clientId, done)

		else:
			done({
				'error': True,
				'message': '%s::%s is not supported' % (handlerClass, command)
			})

# Printer Command Group Handler

class PrinterCommandHandler(object):
	def connect(self, data, clientId, done):
		done(printerManager().connect())

	def pause(self, data, clientId, done):
		printerManager().togglePausePrint()
		done(None)

	def resume(self, data, clientId, done):
		printerManager().togglePausePrint()
		done(None)

	def cancel(self, data, clientId, done):
		done(printerManager().cancelPrint())

	def photo(self, data, clientId, done):

		def doneWithPhoto(pic):
			if pic is not None:
				done({
					'success': True,
					'image_data': base64.b64encode(pic)
				})
			else:
				done({
					'success': False,
					'image_data': ''
				})

		cameraManager().get_pic_async(doneWithPhoto)


# Camera Command Group Handler

class CameraCommandHandler(object):
	def start_video_stream(self, data, clientId, done):
		cameraManager().start_video_stream(done)

	def stop_video_stream(self, data, clientId, done):
		cameraManager().stop_video_stream(done)

# P2P Command Group Handler

class P2PCommandHandler(object):

	def init_connection(self, data, clientId, done):
		#initialize the session on Janus
		#if there is not any session before, Janus is stopped,
		#so it will turn Janus on
		sessionId = webRtcManager().startPeerSession(clientId)

		if sessionId:
			done({
				'success': True,
				'sessionId': sessionId
			})

		else:
			done({
				'error': True,
				'message': 'Unable to start a session'
			})

	def start_plugin(self, data, clientId, done):
		#Manage the plugin and the type of video source: VP8 or H264
		webRtcManager().preparePlugin(data['sessionId'])
		done(None)

	def start_connection(self, data, clientId, done):
		#Start Janus session and it starts to share video
		sessionId = data['sessionId']
		webRtcManager().setSessionDescriptionAndStart(sessionId, data)
		done(None)

	def stop_connection(self, sessionId, clientId, done):
		#Stop Janus session
		#if this is the last (or unique) session in Janus,
		#Janus will be stopped (of course, Gstreamer too)
		webRtcManager().closePeerSession(sessionId)
		done(None)

	def ice_candidate(self, data, clientId, done):
		#Manage the ice candidate for communicating with Janus from client
		if 'sessionId' in data and 'candidate' in data:
			candidate = data['candidate']
			if candidate:
				webRtcManager().tickleIceCandidate(data['sessionId'], candidate['candidate'], candidate['sdpMid'], candidate['sdpMLineIndex'])
			else:
				webRtcManager().reportEndOfIceCandidates(data['sessionId'])

		done(None)
