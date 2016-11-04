# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from gi.repository import Gst

#
#  Base Class for GStreamer Video Source Bin
#

class VideoSrcBinBase(object):
	LOGO_HEIGHT_PERCENT = 0.06 # 6% of the height
	LOGO_ASPECT_RATIO = 0.2

	def __init__(self, pipeline, device, size):
		self._device = device
		self._size = size
		self._bin = pipeline

		lastElement = self._constructSrcChain()

		if not lastElement:
			raise Exception("VideoSrc chain can't be constructed")

		#Now we create the tee, fakesink and link it with the end of the bin
		self.__teeElement = Gst.ElementFactory.make('tee', 'video_src_tee')
		#self.__fakeSinkQueue = Gst.ElementFactory.make('queue', 'fakesink_queue')
		#self.__fakeSink = Gst.ElementFactory.make('fakesink', 'fakesink')
		#self.__fakeSink.set_property('sync', False)

		self._bin.add(self.__teeElement)
		#self._bin.add(self.__fakeSinkQueue)
		#self._bin.add(self.__fakeSink)

		lastElement.link(self.__teeElement)

		#teePad = self.__teeElement.get_request_pad('src_%u')
		#fakesinkPad = self.__fakeSink.get_static_pad('sink')
		#teePad.link(fakesinkPad)
		#fakeSinkQueuePad = self.__fakeSinkQueue.get_static_pad('sink')
		#teePad.link(fakeSinkQueuePad)

		#self.__fakeSinkQueue.link(self.__fakeSink)

	#Creates a request pad on the tee, its corresponing ghost pad on the bin and returns it
	def requestSrcTeePad(self):
		teePad = self.__teeElement.get_request_pad('src_%u')
		return teePad

	@property
	def bin(self):
		return self._bin

	def destroy(self):
		pass

	# ~~~~~~~ Implement these in child classes ~~~~~~~~~~~~~~

	# Creates, adds to the bin and links elements for the source Chain. returns the last element of the chain
	def _constructSrcChain(self):
		pass

