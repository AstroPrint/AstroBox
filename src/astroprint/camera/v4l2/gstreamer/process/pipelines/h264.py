# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from gi.repository import Gst as gst

from .base import GstBasePipeline, PadUnlinker

class GstH264Pipeline(GstBasePipeline):
	def __init__(self, device, size, mainLoop, debugLevel):
		self._udpSinkElement = None
		self._encoderElement = None
		self._encoderCaps = None
		self._rtpElement = None

		self._logger = logging.getLogger(__name__)
		super(GstH264Pipeline, self).__init__(device, size, mainLoop, debugLevel)

	def _getVideoSourceCaps(self):
		return 'video/x-raw,format={ I420, YV12, UYVY, Y41B, Y42B, YVYU, Y444, NV21, NV12, RGB, BGR, RGBx, xRGB, BGRx, xBGR, GRAY8 },width=%d,height=%d' % self._size

	def _setupVideoEncodingPipe(self):
		# ##
		# GSTRAMER MAIN QUEUE: DIRECTLY CONNECTED TO SOURCE
		self._queueVideoElement = gst.ElementFactory.make('queue', None)

		self._encoderElement = gst.ElementFactory.make('omxh264enc', None)

		# CAPABILITIES FOR H264 OUTPUT
		self._encoderCaps = gst.ElementFactory.make("capsfilter", "encoder_filter")
		self._encoderCaps.set_property("caps", gst.Caps.from_string('video/x-h264,profile=high'))

		# VIDEO PAY FOR H264 BEING SHARED IN UDP PACKAGES
		self._rtpElement = gst.ElementFactory.make('rtph264pay', 'rtph264pay')
		self._rtpElement.set_property('pt', 96)
		self._rtpElement.set_property('config-interval', 1)

		# ##
		# MODE FOR BROADCASTING VIDEO
		self._udpSinkElement = gst.ElementFactory.make('udpsink', 'udpsinkvideo')
		self._udpSinkElement.set_property('host', '127.0.0.1')
		self._udpSinkElement.set_property('port', 8004)

		#lock the elements
		self._queueVideoElement.set_locked_state(True)
		self._udpSinkElement.set_locked_state(True)
		self._encoderElement.set_locked_state(True)
		self._encoderCaps.set_locked_state(True)
		self._rtpElement.set_locked_state(True)

		#add to pipeline
		self._pipeline.add(self._queueVideoElement)
		self._pipeline.add(self._encoderElement)
		self._pipeline.add(self._encoderCaps)
		self._pipeline.add(self._rtpElement)
		self._pipeline.add(self._udpSinkElement)

		#link
		self._queueVideoElement.link(self._encoderElement)
		self._encoderElement.link(self._encoderCaps)
		self._encoderCaps.link(self._rtpElement)
		self._rtpElement.link(self._udpSinkElement)

	def _tearDownVideoEncodingPipe(self):
		#remove
		if self._udpSinkElement:
			self._pipeline.remove(self._udpSinkElement)
			self._udpSinkElement = None

		if self._rtpElement:
			self._pipeline.remove(self._rtpElement)
			self._rtpElement = None

		if self._encoderCaps:
			self._pipeline.remove(self._encoderCaps)
			self._encoderCaps = None

		if self._encoderElement:
			self._pipeline.remove(self._encoderElement)
			self._encoderElement = None

		if self._queueVideoElement:
			self._pipeline.remove(self._queueVideoElement)
			self._queueVideoElement = None

	def _attachVideoEncodingPipe(self, doneCallback= None):
		def onPipelineStateChanged(state):
			if doneCallback:
				doneCallback(state is not None)

		self._queueVideoElement.set_state(gst.State.PLAYING)
		self._udpSinkElement.set_state(gst.State.PLAYING)
		self._encoderElement.set_state(gst.State.PLAYING)
		self._encoderCaps.set_state(gst.State.PLAYING)
		self._rtpElement.set_state(gst.State.PLAYING)

		videoQueuePad = self._queueVideoElement.get_static_pad("sink")
		teePadVideoEnc = self._teeElement.get_request_pad("src_%u")
		teePadVideoEnc.link(videoQueuePad)

		self._videoEncQueueLinked = True
		self._handlePipelineStartStop(onPipelineStateChanged)

	def _detachVideoEncodingPipe(self, doneCallback= None):
		#These are used to flush
		chainStartSinkPad = self._queueVideoElement.get_static_pad("sink")
		chainEndSinkPad = self._udpSinkElement.get_static_pad("sink")

		def onPipelineStateChanged(state):
			if doneCallback:
				doneCallback(state is not None)

		def onBlocked(probe):
			teePadVideoEnc = chainStartSinkPad.get_peer()
			self._teeElement.release_request_pad(teePadVideoEnc)
			teePadVideoEnc.remove_probe(probe)

		def onFlushed():
			self._elementStateManager.addStateReq(self._queueVideoElement, gst.State.NULL)
			self._elementStateManager.addStateReq(self._udpSinkElement, gst.State.NULL)
			self._elementStateManager.addStateReq(self._encoderElement, gst.State.NULL)
			self._elementStateManager.addStateReq(self._encoderCaps, gst.State.NULL)
			self._elementStateManager.addStateReq(self._rtpElement, gst.State.NULL)

			self._videoEncQueueLinked = False

			self._handlePipelineStartStop(onPipelineStateChanged)

		unlinker = PadUnlinker(self._teePadVideoEnc, chainStartSinkPad, chainEndSinkPad, onBlocked, onFlushed)
		unlinker.start()
