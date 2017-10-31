# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from gi.repository import Gst

from .base_video_enc import VideoEncBinBase

class VP8VideoEncBin(VideoEncBinBase):
	def __init__(self, size, rotation):
		self._logger = logging.getLogger(__name__)
		super(VP8VideoEncBin, self).__init__(size, rotation)

	def _constructEncChain(self):
		self.__encoderElement = Gst.ElementFactory.make('vp8enc', "vp8_encoder")
		#Setting these values greatly degrades quality of the VP8 video
		#self.__encoderElement.set_property('target-bitrate', 500000)
		#self.__encoderElement.set_property('keyframe-max-dist', 500)
		#####VERY IMPORTANT FOR VP8 ENCODING: NEVER USES deadline = 0 (default value)
		self.__encoderElement.set_property('deadline', 1)

		self.__rtpElement = Gst.ElementFactory.make('rtpvp8pay', 'vp8_rtp')
		self.__rtpElement.set_property('pt', 96)

		self._bin.add(self.__encoderElement)
		self._bin.add(self.__rtpElement)

		self.__encoderElement.link(self.__rtpElement)

		return self.__encoderElement, self.__rtpElement

	def _getUdpPort(self):
		return 8005
