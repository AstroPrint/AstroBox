# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

#Gst Documenation at: https://lazka.github.io/pgi-docs/

try:
	import gi
	gi.require_version('Gst', '1.0')
except ValueError:
	raise ImportError

import logging

from collections import deque

from threading import Event, Thread, Condition, Lock

from gi.repository import Gst

from .bins.photo_capture import PhotoCaptureBin
from .util import waitToReachState

#
#  Base Class for GStreamer Pipeline management
#

class GstBasePipeline(object):
	def __init__(self, device, size, rotation, onFatalError, mainLoop, debugLevel):

		if not Gst.init_check(None):
			raise ImportError

		if debugLevel > 0:
			Gst.debug_set_active(True)
			Gst.debug_set_default_threshold(debugLevel)

		self._onFatalError = onFatalError
		self._mainLop = mainLoop

		self._toreDownAlready = False

		#pipeline control
		self._currentPipelineState = None
		self._pipelineStateCondition = Condition()
		self._photoBinAttachDetachLock = Lock() #Make sure attach and detach operation wait for each other to complete

		self._pipeline = Gst.Pipeline()

		self._videoSrcBin = self._getVideoSrcBin(self._pipeline, device, size, rotation)
		self._videoEncBin = self._getVideoEncBin(size, rotation)
		self._photoCaptureBin = PhotoCaptureBin(self._onNoMorePhotos)

		self._pipeline.add(self._videoEncBin.bin)
		self._pipeline.add(self._photoCaptureBin.bin)

		self._bus = self._pipeline.get_bus()
		self._bus.set_flushing(True)

		self._busListener = BusListener(self._bus)
		self._busListener.addListener(Gst.MessageType.ERROR, self._onBusError)
		self._busListener.addListener(Gst.MessageType.EOS, self._onBusEos)
		self._busListener.addListener(Gst.MessageType.STATE_CHANGED, self._onBusStateChanged)
		self._busListener.addListener(Gst.MessageType.REQUEST_STATE, self._onRequestState)
		self._busListener.start()

	def __del__(self):
		self._logger.info('Pipeline destroyed')

	def __fatalErrorManager(self, details):
		self._onFatalError(details)

	def _attachBin(self, bin):
		return bin.attach(self._videoSrcBin.requestSrcTeePad())

	def _detachBin(self, bin, doneCallback= None):
		bin.detach(doneCallback)

	def _stopPipeline(self, doneCallback= None):
		def onChangeDone():
			if doneCallback:
				doneCallback(True)

			self.tearDown()

		self._pipeline.set_state(Gst.State.NULL)
		onChangeDone()

	def setToPlayAndWait(self):
		if self._currentPipelineState != Gst.State.PLAYING:
			self._pipeline.set_state(Gst.State.PLAYING)

			if waitToReachState(self._pipeline, Gst.State.PLAYING, 10.0, 3):
				self._logger.debug( "Succesfully changed pipeline [%s] state to \033[93mPLAYING\033[0m" % self._pipeline.__class__.__name__)
				self._currentPipelineState = Gst.State.PLAYING
				result = True
			else:
				stateReturn, state, pending = self._pipeline.get_state(1)
				self._logger.error( "Error [%s] to change pipeline state to \033[93mPLAYING\033[0m, stayed on \033[93m%s\033[0m" % (stateReturn.value_name.replace('GST_STATE_CHANGE_',''), state.value_name.replace('GST_STATE_','')) )
				result = False

		else:
			result = True

		return result

	def _onNoMorePhotos(self):
		self._logger.debug('No more photos in Photo Queue')
		waitForDetach = Event()
		def onDetached(success):
			if not waitForDetach.is_set():
				if not success:
					self._logger.warn('There was an error detaching Photos Bin')

				waitForDetach.set()

		self._photoBinAttachDetachLock.acquire()
		self._detachBin(self._photoCaptureBin, onDetached)
		if not waitForDetach.wait(2.0):
			self._logger.warn('Timeout detaching Photos Bin')

		self._photoBinAttachDetachLock.release()

	def tearDown(self):
		if not self._toreDownAlready:
			self._logger.debug("Tearing down...")

			self._busListener.stop()

			stateChange, state, pending = self._pipeline.get_state(1)
			# if it's still trying to change to another state, the following two calls will
			# block so just kill all of it
			if stateChange != Gst.StateChangeReturn.ASYNC:
				self._pipeline.set_state(Gst.State.NULL)
				Gst.deinit()

			self._videoSrcBin = None
			self._videoEncBin = None
			self._photoCaptureBin = None
			self._bus = None

			self._toreDownAlready = True

			if self._mainLop.is_running():
				self._mainLop.quit()

			self._busListener.join()
			self._logger.debug("Tearing down completed")

	def takePhoto(self, doneCallback, text=None):
		if not self._photoCaptureBin.isLinked:
			if self._attachBin(self._photoCaptureBin):
				self._photoCaptureBin.addPhotoReq(text, doneCallback )
			else:
				doneCallback(False)

		else:
			self._photoCaptureBin.addPhotoReq(text, doneCallback)

	def playVideo(self, doneCallback= None):
		if self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)

			return

		result = False
		if self._attachBin(self._videoEncBin):
			if self._videoEncBin.isPlaying:
				result = True
			else:
				self._logger.error('Video Encoding Bin is not playing.')

		if doneCallback:
			doneCallback(result)

	def stopVideo(self, doneCallback= None):
		if not self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)
			return

		if self._videoEncBin.isLinked:
			self._detachBin(self._videoEncBin, doneCallback)

		elif doneCallback:
			doneCallback(True)

	def isVideoStreaming(self):
		return self._videoEncBin.isPlaying

	### Signal Handlers and Callbacks

	def _onBusError(self, msg):
		busError, detail = msg.parse_error()

		self._logger.error("gstreamer error: %s\n--- More Info: ---\n%s\n------------------" % (busError, detail))
		self.__fatalErrorManager(busError.message)

		# KEEP THIS. It might be useful to debug hard to find errors
		'''
		if self._logger.isEnabledFor(logging.DEBUG):
			try:
				Gst.debug_bin_to_dot_file (self._pipeline, Gst.DebugGraphDetails.ALL, "fatal-error")
				self._logger.info( "Gstreamer's pipeline dot file created: %s/fatal-error.dot" % os.getenv("GST_DEBUG_DUMP_DOT_DIR") )

			except:
				self._logger.error("Graphic diagram can not created")
		'''

	def _onBusEos(self, msg):
		self._logger.warn("gstreamer EOS (End of Stream) message received.")
		self.__fatalErrorManager('EOS Received')

	def _onBusStateChanged(self, msg):
		old, new, pending = msg.parse_state_changed()
		self._logger.debug( "\033[90m%20.20s\033[0m: \033[93m%7.7s\033[0m --> \033[93m%s\033[0m --| \033[93m%s\033[0m" % (msg.src.__class__.__name__.replace('__main__.',''), old.value_name.replace('GST_STATE_',''), new.value_name.replace('GST_STATE_',''), pending.value_name.replace('GST_STATE_','')) )

	def _onRequestState(self, msg):
		state = msg.parse_request_state()
		self._logger.debug('%s requested state change to \033[93m%s\033[0m' % (msg.src.__class__.__name__.replace('__main__.',''),  state.value_name.replace('GST_STATE_','')))
		msg.src.set_state(state)

	### Implement these in child clases

	def _getVideoSrcBin(self, pipeline, device, size, rotation):
		pass

	def _getVideoEncBin(self, size, rotation):
		pass


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Util worker threads
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#
#  bus listener and dispatcher
#  It monitor the bus messages and dispatches events to listeners
#

class BusListener(Thread):
	def __init__(self, bus ):
		super(BusListener, self).__init__()
		self._bus = bus
		self._stopped = False
		self._listenersByEvents = {}
		self._listeners = {}
		self._nextId = 1
		self._changeListenersCondition = Condition()

	def run(self):
		while not self._stopped:
			msg = self._bus.timed_pop(Gst.SECOND)
			if not self._stopped and msg:
				t = msg.type

				if t in self._listenersByEvents:
					for l in self._listenersByEvents[t]:
						self._listeners[l][1](msg)

	def stop(self):
		self._stopped = True

	def addListener(self, msgType, callback):
		with self._changeListenersCondition:
			listenerId = self._nextId
			self._nextId += 1
			self._listeners[listenerId] = (msgType, callback)

			if msgType in self._listenersByEvents:
				self._listenersByEvents[msgType].append(listenerId)
			else:
				self._listenersByEvents[msgType] = [listenerId]

			return listenerId

	def removeListener(self, id):
		with self._changeListenersCondition:
			listener = self._listeners[id] #(msgType, callback)
			msgType = listener[0]

			#Remove from the listeners
			listenersByEvent = self._listenersByEvents[msgType]
			listenersByEvent.remove(id)

			if len(listenersByEvent) == 0:
				#We need to remove from the mask
				del self._listenersByEvents[msgType]

