# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from gi.repository import Gst

from . import VideoEncBinBase

class VP8VideoEncBin(VideoEncBinBase):
	def __init__(self):
		self._logger = logging.getLogger(__name__)
		super(VP8VideoEncBin, self).__init__()

	def _constructEncChain(self):
		pass
