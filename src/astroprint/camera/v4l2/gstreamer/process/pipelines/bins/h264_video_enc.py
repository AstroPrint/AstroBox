# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from gi.repository import Gst

from .base_video_enc import VideoEncBinBase

class H264VideoEncBin(VideoEncBinBase):
	def __init__(self):
		self._logger = logging.getLogger(__name__)
		super(H264VideoEncBin, self).__init__()

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

		self.__encoderElement.link(self.__encoderCaps)
		self.__encoderCaps.link(self.__rtpElement)

		return self.__encoderElement, self.__rtpElement

	def _getUdpPort(self):
		return 8004
