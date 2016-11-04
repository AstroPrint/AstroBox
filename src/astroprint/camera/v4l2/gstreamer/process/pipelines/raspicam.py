# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from .base import GstBasePipeline

from .bins.v4l2_video_srd import RaspicamVideoSrcBin
from .bins.h264_video_end import H264VideoEncBin

class GstRaspicamPipeline(GstBasePipeline):
	def __init__(self, device, size, mainLoop, debugLevel):
		self._logger = logging.getLogger(__name__)
		super(GstRaspicamPipeline, self).__init__(device, size, mainLoop, debugLevel)

	def _getVideoSrcBin(pipeline, self, device, size):
		return RaspicamVideoSrcBin(pipeline, device, size)

	def _getVideoEncBin(self):
		return H264VideoEncBin()
