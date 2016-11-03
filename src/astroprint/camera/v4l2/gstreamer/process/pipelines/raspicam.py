# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from .base import GstBasePipeline

class GstRaspicamPipeline(GstBasePipeline):

	def __init__(self, device, size, mainLoop, debugLevel):
		self._logger = logging.getLogger(__name__)
		super(GstRaspicamPipeline, self).__init__(device, size, mainLoop, debugLevel)
