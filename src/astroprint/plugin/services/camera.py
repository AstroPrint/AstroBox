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

		if request.method == 'POST':
			if "application/json" in request.headers["Content-Type"]:
				data = request.json

				if "source" in data:
					s.set(['camera', 'source'], data['source'])

				if "size" in data:
					s.set(['camera', 'size'], data['size'])

				if "encoding" in data:
					s.set(['camera', 'encoding'], data['encoding'])

				if "format" in data:
					s.set(['camera', 'format'], data['format'])

				if "framerate" in data:
					s.set(['camera', 'framerate'], data['framerate'])

				if "video_rotation" in data:
					s.set(['camera', 'video-rotation'], int(data['video_rotation']))

				s.save()

				cm.settingsChanged({
					'size': s.get(['camera', 'size']),
					'encoding': s.get(['camera', 'encoding']),
					'framerate': s.get(['camera', 'framerate']),
					'source': s.get(['camera', 'source']),
					'format': s.get(['camera', 'format']),
					'video_rotation': s.get(['camera', 'video-rotation'])
				})

		return sendResponse(
			encoding= s.get(['camera', 'encoding']),
			size= s.get(['camera', 'size']),
			framerate= s.get(['camera', 'framerate']),
			format= s.get(['camera', 'format']),
			source= s.get(['camera', 'source']),
			video_rotation= s.getInt(['camera', 'video-rotation']),
			structure= cm.settingsStructure()
		)


	def initJanus(self,sendResponse):
		#Start session in Janus
		if webRtcManager().startJanus():
			sendResponse({'success': 'no-error'})

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


		def startStreaming(self,sendResponse):
			webRtcManager().startVideoStream()

			sendResponse({'success': 'no-error'})
