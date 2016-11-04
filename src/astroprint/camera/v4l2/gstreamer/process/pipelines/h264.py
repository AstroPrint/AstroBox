# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from gi.repository import Gst as gst

from .base import GstBasePipeline
from .bins.v4l2_video_src import UsbVideoSrcBin
from .bins.h264_video_enc import H264VideoEncBin

class GstH264Pipeline(GstBasePipeline):
	def __init__(self, device, size, mainLoop, debugLevel):
		self._logger = logging.getLogger(__name__)
		super(GstH264Pipeline, self).__init__(device, size, mainLoop, debugLevel)

	def _getVideoSrcBin(self, pipeline, device, size):
		return UsbVideoSrcBin(pipeline, device, size)

	def _getVideoEncBin(self):
		return H264VideoEncBin()
