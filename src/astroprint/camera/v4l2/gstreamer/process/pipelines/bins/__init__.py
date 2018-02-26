# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from threading import Thread

from gi.repository import Gst

from ..util import waitToReachState

#
#  Base Bin Class for Bin after the Tee
#

class EncoderBin(object):
	def __init__(self, binName):
		self._isLinked = False
		self._bin = Gst.Bin.new(binName)
		self._bin.set_locked_state(True)
		self._logger = logging.getLogger(__name__)

	def attach(self, teePad):
		if self._isLinked:
			return False

		self._bin.set_state(Gst.State.PLAYING)
		self._bin.set_locked_state(False)

		teePad.link(self._bin.get_static_pad('sink'))

		self._isLinked = True
		self._logger.debug('Attached for %s' % self.__class__.__name__)

		return True

	def detach(self, onDone= None):
		if not self._isLinked:
			if onDone:
				onDone(False)

			return

		self._logger.debug('Start detaching %s' % self.__class__.__name__)
		#These are used to flush
		chainStartSinkPad = self._bin.get_static_pad("sink")
		chainEndSinkPad = self._getLastPad()
		teePad = chainStartSinkPad.get_peer()

		def onBlocked(probe):
			self._logger.debug('Pad blocked for %s' % self.__class__.__name__)
			teeElement = teePad.get_parent_element()
			teePad.unlink(chainStartSinkPad)
			teeElement.release_request_pad(teePad)
			# Releasing the request pad removes the probe

		def onFlushed():
			self._logger.debug('Chain Flushed for %s' % self.__class__.__name__)
			self._bin.set_locked_state(True)
			self._bin.get_bus().post(Gst.Message.new_request_state(self._bin, Gst.State.READY))

			if onDone:
				onDone(True)

		self._isLinked = False
		if teePad:
			unlinker = PadUnlinker(teePad, chainStartSinkPad, chainEndSinkPad, onBlocked, onFlushed)
			#unlinker.start()
			unlinker.unlink()
		elif onDone:
			onDone(True) #already detached

	@property
	def bin(self):
		return self._bin

	@property
	def isLinked(self):
		return self._isLinked

	@property
	def isPlaying(self):
		return waitToReachState(self._bin, Gst.State.PLAYING, 1.0, 2)

	# ~~~~~~ Implement these ~~~~~~~~
	def destroy(self):
		pass

	#return the last element of the chain
	def _getLastPad(self):
		pass

#
#  Worker thread to safely unlink a pad
#

class PadUnlinker(object):
	def __init__(self, srcPad, sinkPad, tailSinkPad= None, srcPadBlockedCallback= None, chainFlushedCallback= None):
		#super(PadUnlinker, self).__init__()

		self._srcPad = srcPad
		self._sinkPad = sinkPad
		self._tailSinkPad = tailSinkPad
		self._srcPadBlockedCallback = srcPadBlockedCallback
		self._chainFlushedCallback = chainFlushedCallback
		self._onPadBlockedEvent = None

	#def run()(self):
	def unlink(self):
		self._srcPad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, self._onSrcPadBlocked, None)

	def _onSrcPadBlocked(self, pad, probeInfo, userData):
		if self._srcPadBlockedCallback:
			self._srcPadBlockedCallback(probeInfo.id)

		#Place an event probe at tailSinkPad and send EOS down the chain to flush
		if self._tailSinkPad:
			self._tailSinkPad.add_probe(Gst.PadProbeType.BLOCK | Gst.PadProbeType.EVENT_DOWNSTREAM, self._onTailSinkPadEvent, None)
			self._sinkPad.send_event(Gst.Event.new_eos())

		pad.remove_probe(probeInfo.id)

		return Gst.PadProbeReturn.OK


	def _onTailSinkPadEvent(self, pad, probeInfo, userData):
		eventInfo = probeInfo.get_event()

		if eventInfo.type == Gst.EventType.EOS:
			pad.remove_probe(probeInfo.id)

			if self._chainFlushedCallback:
				self._chainFlushedCallback()

			return Gst.PadProbeReturn.DROP

		else:
			return Gst.PadProbeReturn.PASS
