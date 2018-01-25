# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

from . import PluginService
from octoprint.settings import settings
from octoprint.events import Events

from astroprint.camera import cameraManager
from astroprint.webrtc import webRtcManager

class CameraService(PluginService):
	_validEvents = []

	def __init__(self):
		super(CameraService, self).__init__()

	def connected(self,sendResponse):
		cm = cameraManager()

		return sendResponse({"isCameraConnected": cm.isCameraConnected(), "cameraName": cm.cameraName})


	def isCameraSupportedByAstrobox(self,sendResponse):
		cm = cameraManager()

		return sendResponse({"isCameraSupported": cm.settingsStructure() is not None})


	def hasCameraProperties(self,sendResponse):
		cm = cameraManager()

		return sendResponse({"hasCameraProperties": cm.hasCameraProperties()})

	def cameraSettings(self,sendResponse):
		s = settings()
		cm = cameraManager()

		sendResponse({
				'encoding': s.get(['camera', 'encoding']),
				'size': s.get(['camera', 'size']),
				'framerate': s.get(['camera', 'framerate']),
				'format': s.get(['camera', 'format']),
				'source': s.get(['camera', 'source']),
				'video_rotation': s.getInt(['camera', 'video-rotation']),
				'structure': cm.settingsStructure()
			}
		)


	def initJanus(self,sendResponse):
		#Start session in Janus
		if webRtcManager().startJanus():
			sendResponse({'success': 'no-error'})
		else:
			sendResponse('error_init_janus',True)

	def peerSession(self,data,sendResponse):

		action = data['action']

		if data and 'sessionId' in data:
			sessionId = data['sessionId']

			#if request.method == 'POST':
			if action == 'init_peer_session':
				#Initialize the peer session
				if cameraManager().startLocalVideoSession(sessionId):
					sendResponse({'success': 'no-error'})
				else:
					sendResponse('error_init_peer_session',True)

			#elif request.method == 'DELETE':
			elif action == 'close_peer_session':
				#Close peer session
				if cameraManager().closeLocalVideoSession(sessionId):
					sendResponse({'success': 'no-error'})

				else:
					sendResponse('error_close_peer_session',True)

		else:
			sendResponse('error_no_session_id',True)

	def startStreaming(self,data,sendResponse):
			webRtcManager().startVideoStream()

			sendResponse({'success': 'no-error'})

	def stopStreaming(self,data,sendResponse):

		if cameraManager().closeLocalVideoSession(sessionId):
			sendResponse({'success': 'no-error'})

			return

		else:
			sendResponse({'stop_streaming_error': True})
