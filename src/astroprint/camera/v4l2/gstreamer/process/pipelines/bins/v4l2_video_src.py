# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import platform

from gi.repository import Gst

from .base_video_src import VideoSrcBinBase

from astroprint.manufacturerpkg import manufacturerPkgManager

#
# Base class for V4L2 Based Video sources
#

class V4L2VideoSrcBin(VideoSrcBinBase):
	def __init__(self, pipeline, device, size, rotation):
		distName, distVersion, id = platform.linux_distribution()

		self._linuxDistVersion = int(distVersion.split('.')[0])
		self.__useVideoConvert = self._linuxDistVersion > 9
		self.__videoSourceElement = None
		self.__videoConvertElement = None
		self.__videoLogoElement = None
		self.__videoSourceCaps = None

		super(V4L2VideoSrcBin, self).__init__(pipeline, device, size, rotation)

	# Creates, adds to the bine and links elements for the source Chain. returns the last element of the chain
	def _constructSrcChain(self):
		self.__videoSourceElement = Gst.ElementFactory.make('v4l2src', 'video_source')
		self.__videoSourceElement.set_property("device", self._device)

		if self.__useVideoConvert:
			self.__videoConvertElement = Gst.ElementFactory.make('videoconvert', 'vconvert')

		self.__videoSourceCaps = Gst.ElementFactory.make("capsfilter", "caps_filter")
		self.__videoSourceCaps.set_property("caps", Gst.Caps.from_string(self._getVideoSourceCaps()))

		#Add Elements to the pipeline
		self._bin.add(self.__videoSourceElement)
		self._bin.add(self.__videoSourceCaps)

		if self.__videoConvertElement:
			self._bin.add(self.__videoConvertElement)

		self.__videoSourceElement.link(self.__videoSourceCaps)

		if self.__videoConvertElement:
			self.__videoSourceCaps.link(self.__videoConvertElement)
			lastLink = self.__videoConvertElement
		else:
			lastLink = self.__videoSourceCaps

		width, height = self._size

		#check if we need to rotate the video
		if self._rotation != 0:
			if self._rotation in [1,3]:
				#dimentions are flipped
				height, width = self._size

			self.__videoflipElement = Gst.ElementFactory.make('videoflip', 'videoflip')
			self.__videoflipElement.set_property("method", self._rotation)

			self._bin.add(self.__videoflipElement)
			lastLink.link(self.__videoflipElement)

			lastLink = self.__videoflipElement

		mfWatermark = manufacturerPkgManager().video_watermark

		if mfWatermark is False: #There is no watermark
			return lastLink

		else: # We need to setup a watermark
			logoHeight = round(height * self.LOGO_HEIGHT_PERCENT)
			logoWidth = round(logoHeight / self.LOGO_ASPECT_RATIO)

			# ASTROPRINT'S LOGO FROM DOWN RIGHT CORNER
			self.__videoLogoElement = Gst.ElementFactory.make('gdkpixbufoverlay', 'logo_overlay')

			if mfWatermark is None: # Use AstroPrint's default
				self.__videoLogoElement.set_property('location', '/AstroBox/src/astroprint/static/img/astroprint_logo.png')
			else:
				self.__videoLogoElement.set_property('location', '/AstroBox/src/astroprint/static/img/variant/%s' % mfWatermark)

			self.__videoLogoElement.set_property('overlay-width', logoWidth)
			self.__videoLogoElement.set_property('overlay-height', logoHeight)
			self.__videoLogoElement.set_property('offset-x', width - ( logoWidth + 10 ) )
			self.__videoLogoElement.set_property('offset-y', height - ( logoHeight + 5 ) )

			self._bin.add(self.__videoLogoElement)

			lastLink.link(self.__videoLogoElement)

		return self.__videoLogoElement

	#Implement this in the subclasses below
	def _getVideoSourceCaps(self):
		pass

#
# Base class for USB Based Video sources
#

class UsbVideoSrcBin(V4L2VideoSrcBin):
	def _getVideoSourceCaps(self):
		if self._linuxDistVersion <= 9:
			return 'video/x-raw,format={ I420, YV12, Y41B, Y42B, YVYU, Y444, NV21, NV12, RGB, BGR, RGBx, xRGB, BGRx, xBGR, GRAY8 },width=%d,height=%d,framerate={ 5/1, 10/1, 15/1, 25/1, 30/1 }' % self._size
		else:
			return  'video/x-raw,width=%d,height=%d,framerate={ 5/1, 10/1, 15/1, 25/1, 30/1 }' % self._size
#
# Base class for Raspicam Based Video sources
#

class RaspicamVideoSrcBin(V4L2VideoSrcBin):
	def _getVideoSourceCaps(self):
		if self._linuxDistVersion <= 9:
			return 'video/x-raw,format=I420,width=%d,height=%d,framerate=30/1' % self._size
		else:
			return  'video/x-raw,width=%d,height=%d,framerate=30/1' % self._size
