# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from .base import GstBasePipeline
from .bins.v4l2_video_src import RaspicamVideoSrcBin
from .bins.h264_video_enc import H264VideoEncBin

class GstRaspicamPipeline(GstBasePipeline):
	def __init__(self, device, size, rotation, onFatalError, mainLoop, debugLevel):
		self._logger = logging.getLogger(__name__)
		super(GstRaspicamPipeline, self).__init__(device, size, rotation, onFatalError, mainLoop, debugLevel)

	def _getVideoSrcBin(self, pipeline, device, size, rotation):
		return RaspicamVideoSrcBin(pipeline, device, size, rotation)

	def _getVideoEncBin(self, size, rotation):
		return H264VideoEncBin(size, rotation)
