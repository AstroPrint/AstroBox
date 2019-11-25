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

	@property
	def isPlaying(self):
		return super(ImgVideoEncBin, self).isPlaying and self.__localVideoRecorder.isPlaying()

	def __init__(self, size, rotation, onStopPhotoSeqCallback):
		super(ImgVideoEncBin, self).__init__('img_video_bin')
		self._logger = logging.getLogger(__name__)

		self.__queueLocalVideoImgElement = Gst.ElementFactory.make('queue', 'queue_local_img_video')
		self.__queueLocalVideoImgElement.set_property('silent', True)
		self.__queueLocalVideoImgElement.set_property('max-size-buffers', 1)
		self.__queueLocalVideoImgElement.set_property('leaky', 2) #Leak old buffers


		##################
		self.__videorateLocalVideoElement = Gst.ElementFactory.make('videorate', 'videorate_local_video')
		self.__videorateLocalVideoElement.set_property('max-rate',15)#15fps: https://gstreamer.freedesktop.org/documentation/videorate/index.html#videorate:max-rate
		##################

		##################
		self.__videoscaleLocalVideoElement = Gst.ElementFactory.make('videoscale', 'videoscale_local_video')
		self.__videoscaleLocalVideoElementCaps = Gst.ElementFactory.make("capsfilter", "caps_filter_local_videoscale")
		self.__videoscaleLocalVideoElementCaps.set_property("caps",Gst.Caps.from_string("video/x-raw,format={ I420, YV12, Y41B, Y42B, YVYU, Y444, NV21, NV12, RGB, BGR, RGBx, xRGB, BGRx, xBGR, GRAY8 },width=640,pixel-aspect-ratio=1/1"))
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
		self._bin.add(self.__videoscaleLocalVideoElement)
		self._bin.add(self.__videoscaleLocalVideoElementCaps)
		##################
		self._bin.add(self.__jpegEncElement)
		self._bin.add(self.__videoAppsinkElement)

		#link
		self.__queueLocalVideoImgElement.link(self.__videorateLocalVideoElement)
		##################
		self.__videorateLocalVideoElement.link(self.__videoscaleLocalVideoElement)
		self.__videoscaleLocalVideoElement.link(self.__videoscaleLocalVideoElementCaps)
		self.__videoscaleLocalVideoElementCaps.link(self.__jpegEncElement)
		##################
		self.__jpegEncElement.link(self.__videoAppsinkElement)

		#add a sink pad to the bin
		binSinkPad = Gst.GhostPad.new('sink', self.__queueLocalVideoImgElement.get_static_pad('sink') )
		binSinkPad.set_active(True)
		self._bin.add_pad( binSinkPad )

		self.__localVideoRecorder = PhotoSeqProcessor(self,onStopPhotoSeqCallback)
		self.__localVideoRecorder.start()

	def startLocalVideo(self,callback):
		self.__localVideoRecorder.startLocalVideo(callback)

	def pauseLocalVideo(self):
		self.__localVideoRecorder.pause()

	def destroy(self):
		self.__localVideoRecorder.stopLocalVideo()

	def _getLastPad(self):
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
		self._localVideoReq = None
		self._startRecordingEvent = Event()
		self._photoTakenEvent = Event()
		self._appSink = self._bin.bin.get_by_name('video_appsink')

	def run(self):
		while not self._stopped:
			if self._paused or self._localVideoReq is None:
				self._startRecordingEvent.wait()
				self._startRecordingEvent.clear()

			if not self._stopped and self._localVideoReq is not None:
				while self._localVideoReq:
					if self._stopped:
						return

					self._processPhotoReq()

					if self._paused:
						self._localVideoReq = None


	def isPlaying(self):
		return self._localVideoReq is not None

	def _processPhotoReq(self):
		time.sleep(0.1) #Wait for the pipeline to stabilize with the new values

		sample = None

		self._logger.debug('Request Photo from camera for local video')
		if self.isPlaying():
			sample = self._appSink.emit('pull-sample')
		else:
			sr, state, p = self._appSink.get_state(1)
			self._logger.error( "AppSink is not playing. Currently: \033[93m%s\033[0m" % state.value_name.replace('GST_STATE_','') )

		if sample:
			sampleBuffer = sample.get_buffer()
			success, mapInfo = sampleBuffer.map(Gst.MapFlags.READ)

			if success:
				self._logger.debug('Local frame received. Size (%d)' % mapInfo.size)

				self._localVideoReq(mapInfo.data)

				sampleBuffer.unmap(mapInfo)
				return
			else:
				self._logger.error('Unable to read photo buffer')

		self._localVideoReq(None)

		self._startRecordingEvent.wait(1)

	def startLocalVideo(self,callback):
		if not self._localVideoReq:
			self._localVideoReq = callback
			self._paused = False
			self._startRecordingEvent.set()

	def stopLocalVideo(self):
		self._paused = True
		self._stopped = True
		self._startRecordingEvent.set()
		self._stopPhotoSeqCallback()
		self._localVideoReq = None

	def pause(self):
		self._paused = True
