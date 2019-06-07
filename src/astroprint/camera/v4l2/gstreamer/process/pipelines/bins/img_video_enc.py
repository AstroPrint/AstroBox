# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import time

from threading import Thread, Event
from collections import deque

from gi.repository import Gst

from . import EncoderBin

from ..util import waitToReachState

class ImgVideoEncBin(EncoderBin):

	#@property
	def isPlaying(self):

		a = super(ImgVideoEncBin, self).isPlaying
		b = self.__localVideoRecorder.isPlaying()

		self._logger.info('------')
		self._logger.info(a)
		self._logger.info(b)
		self._logger.info('------')

		return a and b

	def __init__(self, size, rotation, onStopPhotoSeqCallback):
		logging.info('ImgVideoEncBin __init__')
		super(ImgVideoEncBin, self).__init__('img_video_bin')
		self._logger = logging.getLogger(__name__)

		self.__queueLocalVideoImgElement = Gst.ElementFactory.make('queue', 'queue_local_img_video')
		self.__queueLocalVideoImgElement.set_property('silent', True)
		self.__queueLocalVideoImgElement.set_property('max-size-buffers', 1)
		self.__queueLocalVideoImgElement.set_property('leaky', 2) #Leak old buffers


		##################
		self.__videorateLocalVideoElement = Gst.ElementFactory.make('videorate', 'videorate_local_video')
		self.__videorateLocalVideoElementCaps = Gst.ElementFactory.make("capsfilter", "caps_filter_local_video")
		self.__videorateLocalVideoElementCaps.set_property("caps",Gst.Caps.from_string("video/x-raw,format={ I420, YV12, Y41B, Y42B, YVYU, Y444, NV21, NV12, RGB, BGR, RGBx, xRGB, BGRx, xBGR, GRAY8 },framerate=25/1"))
		##################


		self.__jpegEncElement = Gst.ElementFactory.make('jpegenc', 'jpeg_local_video_enc')
		self.__jpegEncElement.set_property('quality', 65)

		self.__videoAppsinkElement = Gst.ElementFactory.make('appsink', 'video_appsink')
		self.__videoAppsinkElement.set_property('max-buffers', 1) # default
		self.__videoAppsinkElement.set_property('drop', True)
		self.__videoAppsinkElement.set_property('sync', True)

		#add
		self._bin.add(self.__queueLocalVideoImgElement)
		##################
		self._bin.add(self.__videorateLocalVideoElement)
		self._bin.add(self.__videorateLocalVideoElementCaps)
		##################
		self._bin.add(self.__jpegEncElement)
		self._bin.add(self.__videoAppsinkElement)

		#link
		#self.__queueLocalVideoImgElement.link(self.__jpegEncElement)
		self.__queueLocalVideoImgElement.link(self.__videorateLocalVideoElement)
		##################
		self.__videorateLocalVideoElement.link(self.__videorateLocalVideoElementCaps)
		self.__videorateLocalVideoElementCaps.link(self.__jpegEncElement)
		##################
		self.__jpegEncElement.link(self.__videoAppsinkElement)

		#add a sink pad to the bin
		binSinkPad = Gst.GhostPad.new('sink', self.__queueLocalVideoImgElement.get_static_pad('sink') )
		binSinkPad.set_active(True)
		self._bin.add_pad( binSinkPad )

		self.__localVideoRecorder = PhotoSeqProcessor(self,onStopPhotoSeqCallback)
		self.__localVideoRecorder.start()

	def addPeersReq(self,id,callback):
		self.__localVideoRecorder.addPeersReq(id,callback)

	def delPeersReq(self,id):
		self.__localVideoRecorder.delPeersReq(id)

	def startLocalVideo(self):
		self._logger.info('startLocalVideo')
		self.__localVideoRecorder.startLocalVideo()

	def pauseLocalVideo(self):
		self._logger.info('pauseLocalVideo')
		self.__localVideoRecorder.pause()

	def destroy(self):
		self._logger.info('destroy')
		self.__localVideoRecorder.stopLocalVideo()

	def _getLastPad(self):
		self._logger.info('_getLastPad')
		return self.__videoAppsinkElement.get_static_pad('sink')

	##################################

#
#  Photo sequence processor. It takes photos until bin is not detached.
#  It runs on a separate thread.
#

class PhotoSeqProcessor(Thread):
	def __init__(self, bin, onStopPhotoSeqCallback ):
		super(PhotoSeqProcessor, self).__init__()

		self.daemon = True
		self._logger = logging.getLogger(__name__+':PhotoSeqProcessor')
		self._stopped = False
		self._paused = False
		self._stopPhotoSeqCallback = onStopPhotoSeqCallback
		self._bin = bin
		self._peersReq = {}
		self._startRecordingEvent = Event()
		self._photoTakenEvent = Event()
		self._appSink = self._bin.bin.get_by_name('video_appsink')
		#self._alreadyExposed = False

	'''def run(self):
		while not self._stopped:
			self._morePhotosEvent.wait()

			if not self._stopped and len(self._photoReqs) > 0:
				while len(self._photoReqs) > 0:
					if self._stopped:
						return

					self._processPhotoReq( self._photoReqs.pop() )

				self._morePhotosEvent.clear()
				self._noMoreReqsCallback()'''


	def run(self):
		while not self._stopped:
			self._logger.info('A')
			self._logger.info(len(self._peersReq))
			self._paused = len(self._peersReq) <= 0

			#if int(time.time()) % 2 != 0:
			#	return

			if self._paused:
				#self._logger.info('B')
				self._startRecordingEvent.wait()

			self._logger.info('C')
			if not self._stopped and len(self._peersReq) > 0:
				self._startRecordingEvent.clear()
				self._logger.info('D')
				while len(self._peersReq) > 0:####???
					self._logger.info('E')
					if self._stopped:
						#self._logger.info('F')
						return

					#self._logger.info('G')
					self._processPhotoReq()


	def isPlaying(self):
		isplaying = waitToReachState(self._appSink, Gst.State.PLAYING, 3.0, 2)

		self._logger.info(isplaying)

		return isplaying

	def _processPhotoReq(self):
		self._logger.info('_processPhotoReq')
		time.sleep(0.1) #Wait for the pipeline to stabilize with the new values

		sample = None

		#if not self._alreadyExposed:
		#	time.sleep(1.5) #give it time to focus and get light. Only on first photo in the sequence
		#	self._alreadyExposed = True

		#self._logger.info('Request Photo from camera for photos sequence')
		if self.isPlaying():
			sample = self._appSink.emit('pull-sample')
		else:
			sr, state, p = self._appSink.get_state(1)
			self._logger.error( "AppSink is not playing. Currently: \033[93m%s\033[0m" % state.value_name.replace('GST_STATE_','') )

		if sample:
			sampleBuffer = sample.get_buffer()
			success, mapInfo = sampleBuffer.map(Gst.MapFlags.READ)

			if success:
				self._logger.info('Photo Received. Size (%d)' % mapInfo.size)

				for id in self._peersReq:
					self._peersReq[id](mapInfo.data)

				sampleBuffer.unmap(mapInfo)
				return
			else:
				self._logger.error('Unable to read photo buffer')

		for id in self._peersReq:
					self._peersReq[id](None)

		self._startRecordingEvent.wait(1)

	def _stop(self):
		self._paused = True
		self._stopped = True
		self._peersReq = {}
		self._startRecordingEvent.set()

	def startLocalVideo(self):
		self._logger.info('startLocalVideo')
		self._startRecordingEvent.set()

	def stopLocalVideo(self):
		self._stop()

	def pause(self):
		self._paused

	def addPeersReq(self,id,callback):
		self._peersReq[id] = callback

		if len(self._peersReq) == 1:
			self.startLocalVideo()

	def delPeersReq(self,id):
		del self._peersReq[id]

		if len(self._peersReq) <= 0:
			self.pause()

