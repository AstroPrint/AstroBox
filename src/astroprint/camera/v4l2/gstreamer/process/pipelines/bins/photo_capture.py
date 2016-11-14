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

#
#  Base Class for GStreamer Photo Capture Bin
#

class PhotoCaptureBin(EncoderBin):
	def __init__(self, onNoMorePhotos):
		self._logger = logging.getLogger(__name__)
		super(PhotoCaptureBin, self).__init__('photo_bin')

		self.__queuePhotoElement = Gst.ElementFactory.make('queue', 'queue_photo')
		self.__queuePhotoElement.set_property('silent', True)
		self.__queuePhotoElement.set_property('max-size-buffers', 1)
		self.__queuePhotoElement.set_property('leaky', 2) #Leak old buffers

		self.__photoTextElement = Gst.ElementFactory.make('textoverlay', 'text_overlay')
		self.__photoTextElement.set_property('valignment', 'top')
		self.__photoTextElement.set_property('ypad', 5)
		self.__photoTextElement.set_property('halignment', 'left')
		self.__photoTextElement.set_property('xpad', 10)

		self.__jpegEncElement = Gst.ElementFactory.make('jpegenc', 'jpeg_enc')
		self.__jpegEncElement.set_property('quality', 65)

		self.__photoAppsinkElement = Gst.ElementFactory.make('appsink', 'photo_appsink')
		self.__photoAppsinkElement.set_property('max-buffers', 1)
		self.__photoAppsinkElement.set_property('drop', True)
		self.__photoAppsinkElement.set_property('sync', True)

		#add
		self._bin.add(self.__queuePhotoElement)
		self._bin.add(self.__photoTextElement)
		self._bin.add(self.__jpegEncElement)
		self._bin.add(self.__photoAppsinkElement)

		#link
		self.__queuePhotoElement.link(self.__photoTextElement)
		self.__photoTextElement.link(self.__jpegEncElement)
		self.__jpegEncElement.link(self.__photoAppsinkElement)

		#add a sink pad to the bin
		binSinkPad = Gst.GhostPad.new('sink', self.__queuePhotoElement.get_static_pad('sink') )
		binSinkPad.set_active(True)
		self._bin.add_pad( binSinkPad )

		self.__reqQueue = PhotoReqsProcessor(self, onNoMorePhotos)
		self.__reqQueue.start()

	def addPhotoReq(self, text, callback):
		self.__reqQueue.addPhotoReq(text, callback)

	def destroy(self):
		self.__reqQueue.stop()

	def _getLastPad(self):
		return self.__photoAppsinkElement.get_static_pad('sink')

#
#  Photo processor. It takes photos from the photo request queue and tries to serve them
#  with the appropiate pipeline. It runs on a separate thread
#

class PhotoReqsProcessor(Thread):
	def __init__(self, bin, noMoreReqsCallback ):
		super(PhotoReqsProcessor, self).__init__()

		self.daemon = True
		self._logger = logging.getLogger(__name__+':PhotoReqsProcessor')
		self._stopped = False
		self._noMoreReqsCallback = noMoreReqsCallback
		self._bin = bin
		self._photoReqs = deque()
		self._morePhotosEvent = Event()
		self._appSink = self._bin.bin.get_by_name('photo_appsink')
		self._photoTextElement = self._bin.bin.get_by_name('text_overlay')
		self._alreadyExposed = False

	def run(self):
		while not self._stopped:
			self._morePhotosEvent.wait()

			if not self._stopped and len(self._photoReqs) > 0:
				while len(self._photoReqs) > 0:
					if self._stopped:
						return

					self._processPhotoReq( self._photoReqs.pop() )

				self._morePhotosEvent.clear()
				self._noMoreReqsCallback()

	def _processPhotoReq(self, req):
		text, reqCallback = req

		if text:
			text = "<span font='arial' weight='bold'>%s</span>" % text
			self._photoTextElement.set_property('text', text)
		else:
			self._photoTextElement.set_property('text', None)

		time.sleep(0.1) #Wait for the pipeline to stabilize with the new values

		sample = None

		if not self._alreadyExposed:
			time.sleep(1.5) #give it time to focus and get light. Only on first photo in the sequence
			self._alreadyExposed = True

		self._logger.debug('Request Photo from camera')
		if waitToReachState(self._appSink, Gst.State.PLAYING, 3.0, 2):
			sample = self._appSink.emit('pull-sample')
		else:
			sr, state, p = self._appSink.get_state(1)
			self._logger.error( "AppSink is not playing. Currently: \033[93m%s\033[0m" % state.value_name.replace('GST_STATE_','') )

		if sample:
			sampleBuffer = sample.get_buffer()
			success, mapInfo = sampleBuffer.map(Gst.MapFlags.READ)

			if success:
				self._logger.debug('Photo Received. Size (%d)' % mapInfo.size)
				reqCallback(mapInfo.data)
				sampleBuffer.unmap(mapInfo)
				return
			else:
				self._logger.error('Unable to read photo buffer')

		reqCallback(None)

	def stop(self):
		self._stopped = True
		self._photoReqs.clear()
		self._morePhotosEvent.set()

	def addPhotoReq(self, text, callback):
		self._photoReqs.appendleft( (text, callback) )
		self._morePhotosEvent.set()
