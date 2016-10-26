# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from astroprint.camera.v4l2.gstreamer.pipelines.base import GstBasePipeline

class GstVp8Pipeline(GstBasePipeline):

	def __init__(self, manager, device, size):
		self._logger = logging.getLogger(__name__)
		super(GstVp8Pipeline, self).__init__(manager, device, size)
