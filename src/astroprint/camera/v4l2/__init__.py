# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import v4l2
import os
import fcntl
import errno
import time
from astroprint.camera import CameraManager
from octoprint.settings import settings

class V4L2Manager(CameraManager):
	def __init__(self, number_of_video_device):
		self.number_of_video_device = number_of_video_device

		if self.isCameraConnected():
			self.supported_formats = self._getSupportedResolutions()
		else:
			self.supported_formats = None

		self.cameraName = self.getCameraName()

		self.cameraInfo = {"name":self.cameraName,"supportedResolutions":self.supported_formats}

		self.setSafeSettings()

		super(V4L2Manager, self).__init__(self.cameraInfo)

	def setSafeSettings(self):

		self.safeRes = None

		fpsArray = []

		cameraConnected = False

		try:
			cameraConnected = os.path.exists("/dev/video%d" % self.number_of_video_device)

		except:

			cameraConnected = False

		if cameraConnected:
			self.supported_formats = self._getSupportedResolutions()
		else:
			self.supported_formats = None

		self.cameraInfo = {"name":self.getCameraName(),"supportedResolutions":self.supported_formats}

		try:
			if self.cameraInfo["supportedResolutions"]:

				for res in self.cameraInfo["supportedResolutions"]:

					pixelformatTranslated = res["pixelformat"]

					if res["pixelformat"]=='YUYV':
						pixelformatTranslated = 'x-raw'

					if pixelformatTranslated == settings().get(["camera", "format"]):#restricted

						resolutionDefault = settings().get(["camera", "size"]).split('x')

			else:
				settings().set(["camera", "encoding"],settings().get(["camera", "encoding"]) or 'h264')
				settings().set(["camera", "size"],self.safeRes)
				settings().set(["camera", "format"],'x-raw')
				self.cameraName = self.getCameraName()

				self.cameraInfo = {"name":self.cameraName,"supportedResolutions":self.supported_formats}

		except:
			self._logger.info('Something went wrong with your camera... any camera connected?')


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
						if pixelformat['pixelformat'] != 'H264':
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

	def _calcMCD(self, a, b):
		if b == 0:
		    return a
		return self._calcMCD(b, a % b)

	def getCameraName(self):

		if  os.path.exists("/dev/video%d" % self.number_of_video_device):

			device = '/dev/video%d' % self.number_of_video_device
			with open(device, 'r') as vd:
				try:
					cp = v4l2.v4l2_capability()
					fcntl.ioctl(vd, v4l2.VIDIOC_QUERYCAP, cp)
					return cp.card
				except:
					return 'unknown'
		else:
			return 'No camera found'

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
				#resolution['description'] = "YUYV"
				#resolution['pixelformat'] = "YUYV"
				#resolution['resolutions'] = [[640, 480]]
				#resolution['pixelformat_int'] = v4l2.v4l2_fmtdesc().pixelformat
				supported_formats.append(resolution)
				return None

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

								if hasattr(framesize.stepwise, 'max_width'):
									max_width = framesize.stepwise.max_width
								else:
									max_width = framesize.stepwise.max_height

								width = framesize.stepwise.min_width
								height = framesize.stepwise.min_height

								stepWidth = framesize.stepwise.step_width
								stepHeight = framesize.stepwise.step_height

								widthCounter = 1
								heightCounter = 1

								"""while width <= max_width:
									while height <= framesize.stepwise.max_height:
										resolutions.append([width,height])
										height = height * stepHeight

									width = width * stepWidth
									height = framesize.stepwise.min_height
								"""


								########## Low resolution #########
								if(self._calcMCD(640,stepWidth) == stepWidth):
									if(self._calcMCD(480,stepHeight) == stepHeight):
										resolutions.append([640L,480L])

								########## High resolution #########
								if(self._calcMCD(1280L,stepWidth) == stepWidth):
									if(self._calcMCD(720L,stepHeight) == stepHeight):
										resolutions.append([1280L,720L])

								break
							framesize.index = framesize.index + 1
					except IOError as e:
						# EINVAL is the ioctl's way of telling us that there are no
						# more formats, so we ignore it
						if e.errno != errno.EINVAL:
							self._logger.error("Unable to determine supported framesizes (resolutions), this may be a driver issue.")
							return None

					supported_format['resolutions'] = resolutions

					for resolution in supported_format['resolutions']:

						frameinterval = v4l2.v4l2_frmivalenum()
						frameinterval.index = 0
						frameinterval.pixel_format = supported_format['pixelformat_int']
						frameinterval.width = resolution[0];
						frameinterval.height = resolution[1];

						framerates = []

						with open(device, 'r') as fd:
							try:
								while fcntl.ioctl(fd,v4l2.VIDIOC_ENUM_FRAMEINTERVALS,frameinterval) != -1:
									if frameinterval.type == v4l2.V4L2_FRMIVAL_TYPE_DISCRETE:
										framerates.append(str(frameinterval.discrete.denominator) + '/' + str(frameinterval.discrete.numerator))
										# for continuous and stepwise, let's just use min and
										# max they use the same structure and only return
										# one result
									stepval = 0
									if frameinterval.type == v4l2.V4L2_FRMIVAL_TYPE_CONTINUOUS:
										stepval = 1

										minval = frameinterval.stepwise.min.denominator/frameinterval.stepwise.min.numerator
										maxval = frameinterval.stepwise.max.denominator/frameinterval.stepwise.max.numerator

										if stepval == 0:
											stepval = frameinterval.stepwise.step.denominator/frameinterval.stepwise.step.numerator

										numerator = frameinterval.stepwise.max.numerator
										denominator = frameinterval.stepwise.max.denominator

										while numerator <= frameinterval.stepwise.min.numerator:
											while denominator <= frameinterval.stepwise.min.denominator:
												framerates.append(str(denominator) + '/' + str(numerator))
												denominator = denominator + frameinterval.stepwise.step.denominator

											numerator = numerator + frameinterval.stepwise.step.numerator
											denominator = frameinterval.stepwise.max.denominator

									elif framesize.type == v4l2.V4L2_FRMSIZE_TYPE_CONTINUOUS or\
										framesize.type == v4l2.V4L2_FRMSIZE_TYPE_STEPWISE:
										minval = frameinterval.stepwise.min.denominator/frameinterval.stepwise.min.numerator
										maxval = frameinterval.stepwise.max.denominator/frameinterval.stepwise.max.numerator
										if stepval == 0:
											stepval = frameinterval.stepwise.step.denominator/frameinterval.stepwise.step.numerator

										for cval in range(minval,maxval):
											framerates.append('1/' + str(cval))

										break
									frameinterval.index = frameinterval.index + 1
							except IOError as e:
								# EINVAL is the ioctl's way of telling us that there are no
								# more formats, so we ignore it
								if e.errno != errno.EINVAL:
									self._logger.error("Unable to determine supported framerates (resolutions), this may be a driver issue.")

						resolution.append(framerates)

			temp = []

			#clean resolutions without FPS: some broken cameras has this configuration
			for resolution in supported_format['resolutions']:
				if len(resolution[2]) > 0:
					temp.append(resolution)

			supported_format['resolutions'] = temp

			try:
				if supported_format['resolutions']:
					return supported_formats
				else:
					return None
			except:
				return None


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

	def reScan(self):
		return self.open_camera()

	def isResolutionSupported(self, resolution, format=None): pass



	def settingsStructure(self,format=None):
		desired = self._desiredSettings

		if len(desired['frameSizes']) > 0:#at least, one resolution of this camera is supported

			if not self.supported_formats:

				self.supported_formats = self._getSupportedResolutions()

			pixelformats = [x['pixelformat'] for x in self.supported_formats]

			for o in desired['cameraOutput']:
				if 	(o['value'] == 'x-mjpeg' and 'MJPG' not in pixelformats) or \
					(o['value'] == 'x-raw' and 'YUYV' not in pixelformats) :
						desired['cameraOutput'].remove(o)

			return desired

		else:#less resolution supported by Astrobox is not supported by this camera

			return None
