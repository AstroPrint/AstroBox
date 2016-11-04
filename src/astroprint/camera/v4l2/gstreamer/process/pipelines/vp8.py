# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from .base import GstBasePipeline

from .bins.v4l2_video_srd import UsbVideoSrcBin
from .bins.h264_video_end import VP8VideoEncBin

class GstVp8Pipeline(GstBasePipeline):
	def __init__(self, device, size, mainLoop, debugLevel):
		self._logger = logging.getLogger(__name__)
		super(GstVp8Pipeline, self).__init__(device, size, mainLoop, debugLevel)

	def _getVideoSrcBin(pipeline, self, device, size):
		return UsbVideoSrcBin(pipeline, device, size)

	def _getVideoEncBin(self):
		return VP8VideoEncBin()
