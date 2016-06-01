# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import v4l2
import os
import fcntl
import errno

from astroprint.camera import CameraManager

class V4L2Manager(CameraManager):
	def __init__(self, number_of_video_device):
		self.number_of_video_device = number_of_video_device
		self.supported_formats = None
		self.cameraName = None

		super(V4L2Manager, self).__init__()

	def __getPixelFormats(self, device, maxformats=5):
	    """Query the camera to see what pixel formats it supports.  A list of
	    dicts is returned consisting of format and description.  The caller
	    should check whether this camera supports VIDEO_CAPTURE before
	    calling this function.
	    """
	    if '/dev/video' not in str(device):
	    	device = '/dev/video' + str(device)

	    supported_formats = []
	    fmt = v4l2.v4l2_fmtdesc()
	    fmt.index = 0
	    fmt.type = v4l2.V4L2_CAP_VIDEO_CAPTURE
	    try:
	        while fmt.index < maxformats:
	            with open(device, 'r') as vd:
	                if fcntl.ioctl(vd, v4l2.VIDIOC_ENUM_FMT, fmt) == 0:
	                    pixelformat = {}
	                    # save the int type for re-use later
	                    pixelformat['pixelformat_int'] = fmt.pixelformat
	                    pixelformat['pixelformat'] = "%s%s%s%s" % \
	                        (chr(fmt.pixelformat & 0xFF),
	                        chr((fmt.pixelformat >> 8) & 0xFF),
	                        chr((fmt.pixelformat >> 16) & 0xFF),
	                        chr((fmt.pixelformat >> 24) & 0xFF))
	                    pixelformat['description'] = fmt.description.decode()
	                    supported_formats.append(pixelformat)
	            fmt.index = fmt.index + 1
	    except IOError as e:
	        # EINVAL is the ioctl's way of telling us that there are no
	        # more formats, so we ignore it
	        if e.errno != errno.EINVAL:
	        	self._logger.error("Unable to determine Pixel Formats, this may be a driver issue.") 

	        return supported_formats
	    return supported_formats

	def _getSupportedResolutions(self):
		"""Query the camera for supported resolutions for a given pixel_format.
		Data is returned in a list of dictionaries with supported pixel
		formats as the following example shows:
		resolution['pixelformat'] = "YUYV"
		resolution['description'] = "(YUV 4:2:2 (YUYV))"
		resolution['resolutions'] = [[width, height], [640, 480], [1280, 720] ]

		If we are unable to gather any information from the driver, then we
		return YUYV and 640x480 which seems to be a safe default. Per the v4l2
		spec the ioctl used here is experimental but seems to be well supported.
		"""
		try:

			device = '/dev/video%d' % self.number_of_video_device
			supported_formats = self.__getPixelFormats(device)

			if not supported_formats:
				resolution = {}
				resolution['description'] = "YUYV"
				resolution['pixelformat'] = "YUYV"
				resolution['resolutions'] = [[640, 480]]
				resolution['pixelformat_int'] = v4l2.v4l2_fmtdesc().pixelformat
				supported_formats.append(resolution)
				return supported_formats

			for supported_format in supported_formats:
			    resolutions = []
			    framesize = v4l2.v4l2_frmsizeenum()
			    framesize.index = 0
			    framesize.pixel_format = supported_format['pixelformat_int']
			    with open(device, 'r') as vd:
			        try:
						cp = v4l2.v4l2_capability()
						fcntl.ioctl(vd, v4l2.VIDIOC_QUERYCAP, cp)
						self.cameraName = cp.card

						while fcntl.ioctl(vd,v4l2.VIDIOC_ENUM_FRAMESIZES,framesize) == 0:
							if framesize.type == v4l2.V4L2_FRMSIZE_TYPE_DISCRETE:
								resolutions.append([framesize.discrete.width,
								framesize.discrete.height])
								# for continuous and stepwise, let's just use min and
								# max they use the same structure and only return
								# one result
							elif framesize.type == v4l2.V4L2_FRMSIZE_TYPE_CONTINUOUS or framesize.type == v4l2.V4L2_FRMSIZE_TYPE_STEPWISE:
								resolutions.append([framesize.stepwise.min_width,
								framesize.stepwise.min_height])
								resolutions.append([framesize.stepwise.max_width,
								framesize.stepwise.max_height])
								break
							framesize.index = framesize.index + 1
			        except IOError as e:
			            # EINVAL is the ioctl's way of telling us that there are no
			            # more formats, so we ignore it
			            if e.errno != errno.EINVAL: 
			                self._logger.error("Unable to determine supported framesizes (resolutions), this may be a driver issue.") 
			                return supported_formats
			    supported_format['resolutions'] = resolutions

			return supported_formats

		except Exception:
			self._logger.info('Camera error: it is not posible to get the camera capabilities', exc_info=True)
			self._broadcastFataError('Camera error: it is not posible to get the camera capabilities. Please, try to reconnect the camera and try again...')
			return None

	def _broadcastFataError(self, msg):
		pass

	@property
	def _desiredSettings(self):
		return {}

	# from CameraManager

	def isCameraConnected(self):
		try:
			return os.path.exists("/dev/video%d" % self.number_of_video_device)
		except:
			return False

	def hasCameraProperties(self):
		return self.supported_formats is not None

	def isResolutionSupported(self, resolution):
		resolutions = []

		for supported_format in self.supported_formats:
		    if supported_format.get('pixelformat') == 'YUYV':
		        resolutions = supported_format.get('resolutions')
		        break

		resolution = [long(e) for e in resolution.split('x')]
		
		return resolution in resolutions

	def settingsStructure(self):
		desired = self._desiredSettings

		if not self.supported_formats:
			self.supported_formats = self._getSupportedResolutions()

		pixelformats = [x['pixelformat'] for x in self.supported_formats]

		for r in desired['frameSizes']:
			if not self.isResolutionSupported(r['value']):
				desired['frameSizes'].remove(r)

		for o in desired['cameraOutput']:
			if 	(o['value'] == 'x-mjpeg' and 'MJPG' not in pixelformats) or \
				(o['value'] == 'x-raw' and 'YUYV' not in pixelformats) or \
				(o['value'] == 'x-h264' and 'H264' not in pixelformats):
					desired['cameraOutput'].remove(o)

		return desired
