# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import subprocess
import time
import gi
import logging

from collections import deque

from threading import Event, Thread, Condition

from gi.repository import Gst as gst, GObject

try:
	gi.require_version('Gst', '1.0')
except ValueError:
	raise ImportError

#
#  Base Class for GStreamer Pipeline management
#

class GstBasePipeline(object):
	LOGO_HEIGHT_PERCENT = 0.06 # 6% of the height
	LOGO_ASPECT_RATIO = 0.2

	def __init__(self, device, size, mainLoop, debugLevel):

		if not gst.init_check(None):
			raise ImportError

		if debugLevel > 0:
			gst.debug_set_active(True)
			gst.debug_set_default_threshold(debugLevel)

		self._mainLop = mainLoop

		self._toreDownAlready = False

		self._videoSourceElement = None
		self._videoLogoElement = None
		self._videoSourceCaps = None
		self._teeElement = None
		self._queueVideoElement = None
		self._queuePhotoElement = None
		self._jpegEncElement = None
		self._photoAppsinkElement = None
		self._photoTextElement = None

		#queue control
		self._videoEncQueueLinked = False
		self._photoQueueLinked = False

		#pipeline control
		self._currentPipelineState = None
		self._pipelineStateCondition = Condition()

		self._device = device
		self._size = size

		self._pipeline = gst.Pipeline()

		self._setupSourceTee()
		self._setupVideoEncodingPipe()
		self._setupPhotoPipe()

		self._bus = self._pipeline.get_bus()
		self._bus.set_flushing(True)

		#setup a listener for bus_errors
		#self._busListener = Thread(target= self._busMessageListener)
		#self._busListener.start()
		self._busListener = BusListener(self._bus)
		self._busListener.addListener(gst.MessageType.ERROR, self._onBusError)
		self._busListener.addListener(gst.MessageType.EOS, self._onBusEos)
		self._busListener.start()

		#Photo Request Queue Management
		self._photoReqsProcessor =  PhotoReqsProcessor( self._pipeline, self._onNoMorePhotoReqs )

		self._elementStateManager = ElementStateManager(self._busListener)
		self._elementStateManager.start()

		self._pipeline.set_state(gst.State.READY)

	def __del__(self):
		self._logger.info('Pipeline destroyed')

	def fatalErrorManager(self):
		self.tearDown()

	#
	#	 Source Tee Pipeline setup
	#

	def _setupSourceTee(self):
		# VIDEO SOURCE DESCRIPTION
		# #DEVICE 0 (FIRST CAMERA) USING v4l2src DRIVER
		# #(v4l2src: VIDEO FOR LINUX TO SOURCE)

		self._videoSourceElement = gst.ElementFactory.make('v4l2src', 'video_source')
		self._videoSourceElement.set_property("device", self._device)

		logoHeight = round(self._size[1] * self.LOGO_HEIGHT_PERCENT)
		logoWidth = round(logoHeight / self.LOGO_ASPECT_RATIO)

		# ASTROPRINT'S LOGO FROM DOWN RIGHT CORNER
		self._videoLogoElement = gst.ElementFactory.make('gdkpixbufoverlay', 'logo_overlay')
		self._videoLogoElement.set_property('location', '/AstroBox/src/astroprint/static/img/astroprint_logo.png')
		self._videoLogoElement.set_property('overlay-width', logoWidth)
		self._videoLogoElement.set_property('overlay-height', logoHeight)
		self._videoLogoElement.set_property('offset-x', self._size[0] - ( logoWidth + 10 ) )
		self._videoLogoElement.set_property('offset-y', self._size[1] - ( logoHeight + 5 ) )

		self._videoSourceCaps = gst.ElementFactory.make("capsfilter", "caps_filter")
		self._videoSourceCaps.set_property("caps", gst.Caps.from_string(self._getVideoSourceCaps()))

		# ##
		# TEE COMMAND IN GSTREAMER ABLES TO JOIN NEW OUTPUT
		# QUEUES TO THE SAME SOURCE
		self._teeElement = gst.ElementFactory.make('tee', 'tee')

		#Add Elements to the pipeline
		self._pipeline.add(self._videoSourceElement)
		self._pipeline.add(self._videoLogoElement)
		self._pipeline.add(self._videoSourceCaps)
		self._pipeline.add(self._teeElement)

		#Link Elements
		self._videoSourceElement.link(self._videoSourceCaps)
		self._videoSourceCaps.link(self._videoLogoElement)
		self._videoLogoElement.link(self._teeElement)

	def _tearDownSourceTee(self):
		#remove elements
		self._pipeline.remove(self._videoSourceElement)
		self._pipeline.remove(self._videoLogoElement)
		self._pipeline.remove(self._videoSourceCaps)
		self._pipeline.remove(self._teeElement)

	#
	#	 Photo (no text) pipeline setup
	#

	def _setupPhotoPipe(self):
		self._jpegEncElement = gst.ElementFactory.make('jpegenc', 'jpegenc')
		self._jpegEncElement.set_property('quality', 65)

		self._photoAppsinkElement = gst.ElementFactory.make('appsink', 'photoAppSink')
		self._photoAppsinkElement.set_property('max-buffers', 1)
		self._photoAppsinkElement.set_property('drop', True)
		self._photoAppsinkElement.set_property('sync', True)

		self._queuePhotoElement = gst.ElementFactory.make('queue', 'queuephoto')
		self._queuePhotoElement.set_property('silent', True)
		self._queuePhotoElement.set_property('max-size-buffers', 1)
		self._queuePhotoElement.set_property('leaky', 2) #Leak old buffers

		self._photoTextElement = gst.ElementFactory.make('textoverlay', 'textOverlay')
		self._photoTextElement.set_property('valignment', 'top')
		self._photoTextElement.set_property('ypad', 5)
		self._photoTextElement.set_property('halignment', 'left')
		self._photoTextElement.set_property('xpad', 10)


		#lock elements
		self._queuePhotoElement.set_locked_state(True)
		self._jpegEncElement.set_locked_state(True)
		self._photoAppsinkElement.set_locked_state(True)
		self._photoTextElement.set_locked_state(True)

		#add
		self._pipeline.add(self._queuePhotoElement)
		self._pipeline.add(self._jpegEncElement)
		self._pipeline.add(self._photoAppsinkElement)
		self._pipeline.add(self._photoTextElement)

		#link
		self._queuePhotoElement.link(self._photoTextElement)
		self._photoTextElement.link(self._jpegEncElement)
		self._jpegEncElement.link(self._photoAppsinkElement)


	def _tearDownPhotoPipe(self):
		if self._queuePhotoElement :
			self._pipeline.remove(self._queuePhotoElement)
			self._queuePhotoElement = None

		if self._photoTextElement:
			self._pipeline.remove(self._photoTextElement)
			self._photoTextElement = None

		if self._jpegEncElement:
			self._pipeline.remove(self._jpegEncElement)
			self._jpegEncElement = None

		if self._photoAppsinkElement:
			self._pipeline.remove(self._photoAppsinkElement)
			self._photoAppsinkElement = None

	def _attachPhotoPipe(self, doneCallback= None):
		if self._photoQueueLinked:
			doneCallback(False)

		def onPipelineStateChanged(state):
			if doneCallback:
				doneCallback(state is not None)

		self._queuePhotoElement.set_state(gst.State.PLAYING)
		self._photoTextElement.set_state(gst.State.PLAYING)
		self._jpegEncElement.set_state(gst.State.PLAYING)
		self._photoAppsinkElement.set_state(gst.State.PLAYING)

		photoQueuePad = self._queuePhotoElement.get_static_pad("sink")
		teePadPhoto = self._teeElement.get_request_pad("src_%u")
		teePadPhoto.link(photoQueuePad)

		self._photoQueueLinked = True

		self._handlePipelineStartStop(onPipelineStateChanged)

	def _detachPhotoPipe(self, doneCallback= None):
		#These are used to flush
		chainStartSinkPad = self._queuePhotoElement.get_static_pad("sink")
		chainEndSinkPad = self._photoAppsinkElement.get_static_pad("sink")

		def onPipelineStateChanged(state):
			if doneCallback:
				doneCallback(state is not None)

		def onBlocked(probe):
			teePadPhoto = chainStartSinkPad.get_peer()
			self._teeElement.release_request_pad(teePadPhoto)
			teePadPhoto.remove_probe(probe)

		def onFlushed():
			self._elementStateManager.addStateReq(self._queuePhotoElement, gst.State.READY)
			self._elementStateManager.addStateReq(self._photoTextElement, gst.State.READY)
			self._elementStateManager.addStateReq(self._photoAppsinkElement, gst.State.READY)
			self._elementStateManager.addStateReq(self._jpegEncElement, gst.State.READY)

			self._photoQueueLinked = False

			self._handlePipelineStartStop(onPipelineStateChanged)

		unlinker = PadUnlinker(chainStartSinkPad.get_peer(), chainStartSinkPad, chainEndSinkPad, onBlocked, onFlushed)
		unlinker.start()

	def _stopPipeline(self, doneCallback= None):
		def onChangeDone():
			if doneCallback:
				doneCallback(True)

			self.tearDown()

		self._elementStateManager.addStateReq(self._pipeline, gst.State.NULL, onChangeDone)

	def _handlePipelineStartStop(self, doneCallback= None):
		with self._pipelineStateCondition:
			newPipelineState = None

			if self._videoEncQueueLinked or self._photoQueueLinked:
				#stream needs to flow
				newPipelineState = gst.State.PLAYING

			else:
				#stream needs to stop
				def onChangeDone():
					self.tearDown()

				self._elementStateManager.addStateReq(self._pipeline, gst.State.NULL, onChangeDone)
				return

			if self._currentPipelineState != newPipelineState:
				def onChangeDone(state):
					self._currentPipelineState = state

					if doneCallback:
						doneCallback(state)

				self._elementStateManager.addStateReq(self._pipeline, newPipelineState, onChangeDone)

			elif doneCallback: #no change needed
				doneCallback(newPipelineState)

	def tearDown(self):
		if not self._toreDownAlready:
			self._logger.info("Tearing down...")

			self._photoReqsProcessor.stop()
			self._elementStateManager.stop()
			self._busListener.stop()

			self._tearDownSourceTee()
			self._tearDownVideoEncodingPipe()
			self._tearDownPhotoPipe()

			self._pipeline.set_state(gst.State.NULL)
			self._bus = None

			self._toreDownAlready = True

			if self._mainLop.is_running():
				self._mainLop.quit()

	def takePhoto(self, doneCallback, text=None):
		if not self._photoReqsProcessor.isAlive():
			try:
				self._photoReqsProcessor.start()
			except RuntimeError:
				self._photoReqsProcessor = PhotoReqsProcessor( self._pipeline, self._onNoMorePhotoReqs )
				self._photoReqsProcessor.start()

		if self._photoReqsProcessor.isAlive():
			if not self._photoQueueLinked:
				def onAttachDone(success):
					self._logger.info('attached %s' % success)

					if success:
						self._photoReqsProcessor.addPhotoReq(text, not self._videoEncQueueLinked, doneCallback)

				self._logger.info('About to attach')
				self._attachPhotoPipe(onAttachDone)

			else:
				self._photoReqsProcessor.addPhotoReq(text, not self._videoEncQueueLinked, doneCallback)

		else:
			doneCallback(None)

	def playVideo(self, doneCallback= None):
		if self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)

			return

		if not self._videoEncQueueLinked:
			try:
				self._attachVideoEncodingPipe(doneCallback)

			except Exception, error:
				self._logger.error("Error starting video stream: %s" % str(error), exc_info = True)
				self._pipeline.set_state(gst.State.NULL)
				self._currentPipelineState = gst.State.NULL

				if doneCallback:
					doneCallback(False)

		elif doneCallback:
			doneCallback(True)

	def stopVideo(self, doneCallback= None):
		if not self.isVideoStreaming():
			if doneCallback:
				doneCallback(True)
			return

		if self._videoEncQueueLinked:
			if self._photoQueueLinked:
				self._detachVideoEncodingPipe(doneCallback)
			else:
				self._stopPipeline(doneCallback)

		elif doneCallback:
			doneCallback(True)

	def isVideoStreaming(self):
		return self._videoEncQueueLinked and self._currentPipelineState == gst.State.PLAYING

	### Signal Handlers and Callbacks

	def _onBusError(self, msg):
		busError, detail = msg.parse_error()

		self._logger.error("gstreamer error: %s\n--- More Info: ---\n%s\n------------------" % (busError, detail))

		if busError.code == 1: #Internal Data Flow Error
			self.tearDown()

	def _onBusEos(self, msg):
		self._logger.info("gstreamer EOS (End of Stream) message received.")

	'''
	def _busMessageListener(self):
		while self._bus:
			msg = self._bus.timed_pop_filtered(1 * gst.SECOND, gst.MessageType.ERROR | gst.MessageType.EOS ) #| gst.MessageType.STATE_CHANGED)
			if msg:
				t = msg.type

				if t == gst.MessageType.ERROR:
					busError, detail = msg.parse_error()

					self._logger.error("gstreamer error: %s\n--- More Info: ---\n%s\n------------------" % (busError, detail))

					if busError.code == 1: #Internal Data Flow Error
						self.tearDown()
						return

				elif t == gst.MessageType.EOS:
					self._logger.info("gstreamer EOS (End of Stream) message received.")

				#elif t == gst.MessageType.STATE_CHANGED:
				#	old, new, pending = msg.parse_state_changed()
				#	self._logger.info( "\033[90m%s\033[0m changing from \033[93m%s\033[0m to \033[93m%s\033[0m" % (msg.src, old, new) )
		'''

	def _onNoMorePhotoReqs(self):
		#start photo queue detachemnt
		if self._videoEncQueueLinked:
			self._detachPhotoPipe()
		else:
			self._stopPipeline()

	### Implement these in child clases

	def _getVideoSourceCaps(self):
		pass

	def _setupVideoEncodingPipe(self):
		pass

	def _tearDownVideoEncodingPipe(self):
		pass

	def _attachVideoEncodingPipe(self, doneCallback= None):
		pass

	def _detachVideoEncodingPipe(self, doneCallback= None):
		pass

#
#  Pipeline State Manager
#

class ElementStateManager(Thread):
	def __init__(self, busListener):
		super(ElementStateManager, self).__init__()

		self.daemon = True
		self._logger = logging.getLogger(__name__+':ElementStateManager')
		self._stopped = False
		self._currentState = None
		self._newStateAvailableEvent = Event()
		self._stateReqs = deque()
		self._currentReq = None
		self._busListener = busListener
		self._pendingReqs = {}

	def run(self):
		busListenerId = self._busListener.addListener(gst.MessageType.STATE_CHANGED, self._onStateChanged)

		while not self._stopped:
			self._newStateAvailableEvent.wait()

			if not self._stopped and len(self._stateReqs) > 0:
				while len(self._stateReqs) > 0:
					if self._stopped:
						return

					req = self._stateReqs.pop()
					targetState = req['state']
					element = req['element']
					cb = req['callback']

					#self._logger.info( "Requesting state %s for %s" % (targetState, element) )
					element.set_state(targetState)

					if cb:
						if element in self._pendingReqs:
							self._pendingReqs[element][targetState] = cb
						else:
							self._pendingReqs[element] = {targetState: cb}

			self._newStateAvailableEvent.clear()

		self._busListener.removeListener(busListenerId)

	def _onStateChanged(self, msg):
		old, new, pending = msg.parse_state_changed()
		self._logger.info( "\033[90m%s\033[0m changing from \033[93m%s\033[0m to \033[93m%s\033[0m" % (msg.src, old, new) )

		if msg.src in self._pendingReqs:
			pendingForElement = self._pendingReqs[msg.src]

			if pending == gst.State.VOID_PENDING and new in pendingForElement:
				if new in pendingForElement:
					pendingForElement[new](new)
					del pendingForElement[new]
					if not pendingForElement:
						del self._pendingReqs[msg.src]

	def _onBusMessage(self, msg):
		if msg.src in self._pendingReqs:
			pendingForElement = self._pendingReqs[msg.src]
			print pendingForElement

			old, new, pending = msg.parse_state_changed()
			self._logger.info( "\033[90m%s\033[0m changing from \033[93m%s\033[0m to \033[93m%s\033[0m" % (msg.src, old, new) )

			if pending == gst.State.VOID_PENDING and new in pendingForElement:
				pendingForElement[new](new)
				del pendingForElement[new]
				print pendingForElement
				if not pendingForElement:
					del self._pendingReqs[msg.src]

		else:
			print msg.src

	def stop(self):
		self._stopped = True
		self._stateReqs.clear()
		self._newStateAvailableEvent.set()

	def addStateReq(self, element, state, callback = None):
		self._stateReqs.appendleft({ 'element': element, 'state': state, 'callback': callback })
		self._newStateAvailableEvent.set()

#
#  Worker thread to safely unlink a pad
#

class PadUnlinker(Thread):
	def __init__(self, srcPad, sinkPad, tailSinkPad= None, srcPadBlockedCallback= None, chainFlushedCallback= None):
		super(PadUnlinker, self).__init__()

		self._srcPad = srcPad
		self._sinkPad = sinkPad
		self._tailSinkPad = tailSinkPad
		self._srcPadBlockedCallback = srcPadBlockedCallback
		self._chainFlushedCallback = chainFlushedCallback
		self._onPadBlockedEvent = None

	def run(self):
		self._srcPad.add_probe(gst.PadProbeType.BLOCK_DOWNSTREAM, self._onSrcPadBlocked, None)

	def _onSrcPadBlocked(self, pad, probeInfo, userData):
		if self._srcPadBlockedCallback:
			self._srcPadBlockedCallback(probeInfo.id)

		#Place an event probe at tailSinkPad and send EOS down the chain to flush
		if self._tailSinkPad:
			self._tailSinkPad.add_probe(gst.PadProbeType.BLOCK | gst.PadProbeType.EVENT_DOWNSTREAM, self._onTailSinkPadEvent, None)
			self._sinkPad.send_event(gst.Event.new_eos())

		return gst.PadProbeReturn.OK


	def _onTailSinkPadEvent(self, pad, probeInfo, userData):
		eventInfo = probeInfo.get_event()

		if eventInfo.type == gst.EventType.EOS:
			pad.remove_probe(probeInfo.id)

			if self._chainFlushedCallback:
				self._chainFlushedCallback()

			return gst.PadProbeReturn.DROP

		else:
			return gst.PadProbeReturn.PASS


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
		self._photoQueue = self._pipeline.get_by_name('queuephoto')
		self._jpegEnc = self._pipeline.get_by_name('jpegenc')
		self._appSink = self._pipeline.get_by_name('photoAppSink')
		self._photoTextElement = self._pipeline.get_by_name('textOverlay')

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
		text = req['text']

		if text:
			text = "<span font='arial' weight='bold'>%s</span>" % text
			self._photoTextElement.set_property('text', text)
		else:
			self._photoTextElement.set_property('text', None)

		time.sleep(0.1) #Wait for the pipeline to stabilize with the new values

		reqCallback = req['callback']
		needsExposure = req['needsExposure']

		sample = None
		photoBuffer = None
		tries = 3

		while not sample and tries > 0:
			if needsExposure:
				time.sleep(1.5) #give it time to focus and get light. Only on first photo in the sequence

			self._logger.info('Request Photo from camera')
			sample = self._appSink.emit('pull-sample')

			if sample:
				photoBuffer = sample.get_buffer().map(gst.MapFlags.READ)[1].data
				break;
			else:
				tries -= 1

		self._logger.info('Photo Received. Size (%d)' % len(photoBuffer) if photoBuffer is not None else 0)
		reqCallback(photoBuffer)

	def stop(self):
		self._photoReqs.clear()
		self._morePhotosEvent.set()
		self._stopped = True

	def addPhotoReq(self, text, needsExposure, callback):
		self._logger.info('Adding Photo Req: text ( %s ), needsExposure ( %s ), callback ( %s )' % (text, needsExposure, callback))
		self._photoReqs.appendleft({ 'text': text, 'needsExposure': needsExposure, 'callback': callback })
		self._morePhotosEvent.set()

#
#  bus listener and dispatcher
#  It monitor the bus messages and dispatches events to listeners
#

class BusListener(Thread):
	def __init__(self, bus ):
		super(BusListener, self).__init__()
		self._bus = bus
		self._stopped = False
		self._relevantMessages = []
		self._relevantMessagesMask = gst.MessageType.UNKNOWN
		self._listenersByEvents = {}
		self._listeners = {}
		self._nextId = 1
		self._changeListenersCondition = Condition()

	def run(self):
		while not self._stopped:
			print self._relevantMessagesMask
			msg = self._bus.timed_pop_filtered(gst.SECOND, self._relevantMessagesMask) #1 sec timeout
			if not self._stopped and msg:
				t = msg.type

				for l in self._listenersByEvents[t]:
					self._listeners[l][1](msg)

	def _recalculateMask(self):
		self._relevantMessagesMask = gst.MessageType.UNKNOWN
		for mask in self._relevantMessages:
			self._relevantMessagesMask |= mask

	def stop(self):
		self._stopped = True

	def addListener(self, msgType, callback):
		with self._changeListenersCondition:
			if msgType not in self._relevantMessages:
				self._relevantMessages.append(msgType)
				self._recalculateMask()

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
				self._relevantMessages.remove(msgType)
				self._recalculateMask()

