# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from .base import GstBasePipeline
from .bins.v4l2_video_src import UsbVideoSrcBin
from .bins.vp8_video_enc import VP8VideoEncBin

class GstVp8Pipeline(GstBasePipeline):
	def __init__(self, device, size, rotation, onFatalError, mainLoop, debugLevel):
		self._logger = logging.getLogger(__name__)
		super(GstVp8Pipeline, self).__init__(device, size, rotation, onFatalError, mainLoop, debugLevel)

	def _getVideoSrcBin(self, pipeline, device, size, rotation):
		return UsbVideoSrcBin(pipeline, device, size, rotation)

	def _getVideoEncBin(self, size, rotation):
		return VP8VideoEncBin(size, rotation)
