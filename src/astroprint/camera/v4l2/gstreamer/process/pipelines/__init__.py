# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

class InvalidGStreamerPipelineException(Exception):
    pass

def pipelineFactory(device, size, rotation, source, encoder, onFatalError, mainLoop, debugLevel):
	if source == 'usb':
		if encoder == 'h264':
			from .h264 import GstH264Pipeline
			return GstH264Pipeline(device, size, rotation, onFatalError, mainLoop, debugLevel)

		elif encoder == 'vp8': # VP8
			from .vp8 import GstVp8Pipeline
			return GstVp8Pipeline(device, size, rotation, onFatalError, mainLoop, debugLevel)

	elif source == 'raspicam': #Raspicam
		from .raspicam import GstRaspicamPipeline
		return GstRaspicamPipeline(device, size, rotation, onFatalError, mainLoop, debugLevel)

	raise InvalidGStreamerPipelineException('Invalid source [%s] and encodder [%s] combination' % (source, encoder))
