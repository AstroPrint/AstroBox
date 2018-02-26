# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from gi.repository import Gst

from .base_video_enc import VideoEncBinBase

class H264VideoEncBin(VideoEncBinBase):
	def __init__(self, size, rotation):
		super(H264VideoEncBin, self).__init__(size, rotation)
		self._logger = logging.getLogger(__name__)

	def _constructEncChain(self):
		self.__encoderElement = Gst.ElementFactory.make('omxh264enc', 'h264_encoder')

		# CAPABILITIES FOR H264 OUTPUT
		self.__encoderCaps = Gst.ElementFactory.make("capsfilter", "encoder_filter")
		self.__encoderCaps.set_property("caps", Gst.Caps.from_string('video/x-h264,profile=high'))

		# VIDEO PAY FOR H264 BEING SHARED IN UDP PACKAGES
		self.__rtpElement = Gst.ElementFactory.make('rtph264pay', 'h264_rtp')
		self.__rtpElement.set_property('pt', 96)
		self.__rtpElement.set_property('config-interval', 1)

		self._bin.add(self.__encoderElement)
		self._bin.add(self.__encoderCaps)
		self._bin.add(self.__rtpElement)

		#H264 created weird gree/red bands when the the size is not divisible by 16
		#We should crop to the closes if that happens
		first_element = None

		if self._rotation in [1,3]:
			#dimentions are flipped
			height, width = self._size
		else:
			width, height = self._size

		modulo_w = width % 16
		modulo_h = height % 16
		if modulo_w > 0 or modulo_h > 0:
			self.__cropElement = Gst.ElementFactory.make('videocrop', 'videocrop')
			if modulo_w > 0:
				half_w = modulo_w/2
				self.__cropElement.set_property('left', half_w)
				self.__cropElement.set_property('right', modulo_w - half_w)

			if modulo_h > 0:
				half_h = modulo_h/2
				self.__cropElement.set_property('top', half_h)
				self.__cropElement.set_property('bottom', modulo_h - half_h)

			self._bin.add(self.__cropElement)
			self.__cropElement.link(self.__encoderElement)
			first_element = self.__cropElement

		else:
			first_element = self.__encoderElement

		self.__encoderElement.link(self.__encoderCaps)
		self.__encoderCaps.link(self.__rtpElement)

		return first_element, self.__rtpElement

	def _getUdpPort(self):
		return 8004
