# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from gi.repository import Gst

from . import EncoderBin

#
#  Base Class for GStreamer Video Encoding Bin
#

class VideoEncBinBase(EncoderBin):
	def __init__(self, size, rotation):
		self._size = size
		self._rotation = rotation
		super(VideoEncBinBase, self).__init__('video_enc_bin')

		firstElement, lastElement = self._constructEncChain()

		if not firstElement or not lastElement:
			raise Exception("VideoEnc chain can't be constructed")

		self.__queueVideoElement = Gst.ElementFactory.make('queue', 'video_enc_queue')
		self.__queueVideoElement.set_property('silent', True)

		self.__udpSinkElement = Gst.ElementFactory.make('udpsink', 'udp_sink_video')
		self.__udpSinkElement.set_property('host', '127.0.0.1')
		self.__udpSinkElement.set_property('port', self._getUdpPort())

		#add to pipeline
		self._bin.add(self.__queueVideoElement)
		self._bin.add(self.__udpSinkElement)

		#link
		self.__queueVideoElement.link(firstElement)
		lastElement.link(self.__udpSinkElement)

		#add a sink pad to the bin
		binSinkPad = Gst.GhostPad.new('sink', self.__queueVideoElement.get_static_pad('sink') )
		binSinkPad.set_active(True)
		self._bin.add_pad( binSinkPad )

	def _getLastPad(self):
		return self.__udpSinkElement.get_static_pad('sink')

	# ~~~~~~~ Implement these in child classes ~~~~~~~~~~~~~~

	# Creates, adds to the bin and links elements for the source Chain. returns a tupe (first, last) elements of the chain
	def _constructEncChain(self):
		pass

	def _getUdpPort(self):
		raise NotImplementedError()

