# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import logging

from gi.repository import Gst as gst

from astroprint.camera.v4l2.gstreamer.pipelines.base import GstBasePipeline

class GstH264Pipeline(GstBasePipeline):
	def __init__(self, manager, device, size):
		self._udpSinkElement = None
		self._encoderElement = None
		self._encoderCaps = None
		self._rtpElement = None

		self._logger = logging.getLogger(__name__)
		super(GstH264Pipeline, self).__init__(manager, device, size)

	def _getVideoSourceCaps(self):
		return 'video/x-raw,format=I420,width=%s,height=%s' % self._size

	def _setupVideoEncodingPipe(self):
		# ##
		# GSTRAMER MAIN QUEUE: DIRECTLY CONNECTED TO SOURCE
		self._queueVideoElement = gst.ElementFactory.make('queue', None)

		self._encoderElement = gst.ElementFactory.make('omxh264enc', None)

		# CAPABILITIES FOR H264 OUTPUT
		self._encoderCaps = gst.ElementFactory.make("capsfilter", "encoder_filter")
		self._encoderCaps.set_property("caps", gst.Caps.from_string('video/x-h264,profile=high'))

		# VIDEO PAY FOR H264 BEING SHARED IN UDP PACKAGES
		self._rtpElement = gst.ElementFactory.make('rtph264pay', 'rtph264pay')
		self._rtpElement.set_property('pt', 96)
		self._rtpElement.set_property('config-interval', 1)

		# ##
		# MODE FOR BROADCASTING VIDEO
		self._udpSinkElement = gst.ElementFactory.make('udpsink', 'udpsinkvideo')
		self._udpSinkElement.set_property('host', '127.0.0.1')
		self._udpSinkElement.set_property('port', 8004)

		#add to pipeline
		self._pipeline.add(self._queueVideoElement)
		self._pipeline.add(self._encoderElement)
		self._pipeline.add(self._encoderCaps)
		self._pipeline.add(self._rtpElement)
		self._pipeline.add(self._udpSinkElement)

		#link
		self._queueVideoElement.link(self._encoderElement)
		self._encoderElement.link(self._encoderCaps)
		self._encoderCaps.link(self._rtpElement)
		self._rtpElement.link(self._udpSinkElement)

	def _tearDownVideoEncodingPipe(self):
		#unlink
		#I think unlink happens automatically when removing
		#self._rtpElement.unlink(self._udpSinkElement)
		#self._encoderCaps.unlink(self._rtpElement)
		#self._encoderElement.unlink(self._encoderCaps)
		#self._queueVideoElement.unlink(self._encoderElement)

		#remove
		self._pipeline.remove(self._udpSinkElement)
		self._pipeline.remove(self._rtpElement)
		self._pipeline.remove(self._encoderCaps)
		self._pipeline.remove(self._encoderElement)
		self._pipeline.remove(self._queueVideoElement)

		#Free memory
		self._queueVideoElement = None
		self._udpSinkElement = None
		self._encoderElement = None
		self._encoderCaps = None
		self._rtpElement = None
