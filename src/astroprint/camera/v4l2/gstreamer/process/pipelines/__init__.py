# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

from .h264 import GstH264Pipeline
from .vp8 import GstVp8Pipeline
from .raspicam import GstRaspicamPipeline

def pipelineFactory(device, size, source, encoder, mainLoop, debugLevel):
	if source.lower() == 'usb':
		if encoder.lower() == 'h264':
			return GstH264Pipeline(device, size, mainLoop, debugLevel)
		else: # VP8
			return GstVp8Pipeline(device, size, mainLoop, debugLevel)

	else: #Raspicam
		return GstRaspicamPipeline(device, size, mainLoop, debugLevel)
