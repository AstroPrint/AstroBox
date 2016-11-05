# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging
import time

from threading import Thread, Event
from collections import deque

from gi.repository import Gst

from . import EncoderBin

#
#  Base Class for GStreamer Photo Capture Bin
#

class PhotoCaptureBin(EncoderBin):
	def __init__(self):
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

		self.__reqQueue = PhotoReqsProcessor(self._bin, self.__onNoMorePhotos)
		self.__reqQueue.start()

	def __onNoMorePhotos(self):
		self._logger.debug('No more photos in Queue')
		self.detach()

	def addPhotoReq(self, text, needsExposure, callback):
		self.__reqQueue.addPhotoReq(text, needsExposure, callback)

	def destroy(self):
		self.__reqQueue.stop()

	def _getLastPad(self):
		return self.__photoAppsinkElement.get_static_pad('sink')

#
#  Photo processor. It takes photos from the photo request queue and tries to serve them
#  with the appropiate pipeline. It runs on a separate thread
#

class PhotoReqsProcessor(Thread):
	def __init__(self, pipeline, noMoreReqsCallback ):
		super(PhotoReqsProcessor, self).__init__()

		self.daemon = True
		self._logger = logging.getLogger(__name__+':PhotoReqsProcessor')
		self._stopped = False
		self._noMoreReqsCallback = noMoreReqsCallback
		self._pipeline = pipeline
		self._photoReqs = deque()
		self._morePhotosEvent = Event()
		self._photoQueue = self._pipeline.get_by_name('queue_photo')
		self._appSink = self._pipeline.get_by_name('photo_appsink')
		self._photoTextElement = self._pipeline.get_by_name('text_overlay')
		self._alreadyExposed = False

	def run(self):
		while not self._stopped:
			self._morePhotosEvent.wait()

			if not self._stopped and len(self._photoReqs) > 0:
				while len(self._photoReqs) > 0:
					if self._stopped:
						return

					self._processPhotoReq( self._photoReqs.pop() )

				self._alreadyExposed = False
				self._morePhotosEvent.clear()
				self._noMoreReqsCallback()

	def _processPhotoReq(self, req):
		text, needsExposure, reqCallback = req

		if text:
			text = "<span font='arial' weight='bold'>%s</span>" % text
			self._photoTextElement.set_property('text', text)
		else:
			self._photoTextElement.set_property('text', None)

		time.sleep(0.1) #Wait for the pipeline to stabilize with the new values

		sample = None
		photoBuffer = None

		if needsExposure and not self._alreadyExposed:
			time.sleep(1.5) #give it time to focus and get light. Only on first photo in the sequence
			self._alreadyExposed = True

		self._logger.debug('Request Photo from camera')
		stateReturn, state, pending = self._appSink.get_state(1.5 * Gst.SECOND)
		if state == Gst.State.PLAYING and ( stateReturn == Gst.StateChangeReturn.SUCCESS or stateReturn == Gst.StateChangeReturn.NO_PREROLL ):
			sample = self._appSink.emit('pull-sample')
		else:
			self._logger.error( "AppSink is not playing. Currently: \033[93m%s\033[0m" % state.value_name.replace('GST_STATE_','') )

		if sample:
			photoBuffer = sample.get_buffer().map(Gst.MapFlags.READ)[1].data
			self._logger.debug('Photo Received. Size (%d)' % (len(photoBuffer) if photoBuffer is not None else 0))

		reqCallback(photoBuffer)

	def stop(self):
		self._stopped = True
		self._photoReqs.clear()
		self._morePhotosEvent.set()

	def addPhotoReq(self, text, needsExposure, callback):
		self._photoReqs.appendleft( (text, needsExposure, callback) )
		self._morePhotosEvent.set()
