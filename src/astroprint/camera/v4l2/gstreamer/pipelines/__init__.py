# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from astroprint.camera.v4l2.gstreamer.pipelines.h264 import GstH264Pipeline
from astroprint.camera.v4l2.gstreamer.pipelines.vp8 import GstVp8Pipeline
from astroprint.camera.v4l2.gstreamer.pipelines.raspicam import GstRaspicamPipeline

def pipelineFactory(manager, deviceId, size, source, encoder):
	if source == 'USB':
		if encoder == 'h264':
			return GstH264Pipeline(manager, deviceId, size)
		else: # VP8
			return GstVp8Pipeline(manager, deviceId, size)

	else: #Raspicam
		return GstRaspicamPipeline(manager, deviceId, size)
