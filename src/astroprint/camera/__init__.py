# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

# singleton
_instance = None

def cameraManager():
	global _instance
	if _instance is None:
		if platform == "linux" or platform == "linux2":
			number_of_video_device = 0#/dev/video``0´´

			from astroprint.camera.gstreamer import GStreamerManager
			_instance = GStreamerManager(number_of_video_device)
		elif platform == "darwin":
			from astroprint.camera.mac import CameraMacManager
			_instance = CameraMacManager()
			
	return _instance

import threading
import os.path
import time
import logging
import v4l2
import errno
import fcntl

from sys import platform

from octoprint.settings import settings
from octoprint.events import eventManager, Events
from astroprint.cloud import astroprintCloud
from astroprint.printer.manager import printerManager

class TimelapseWorker(threading.Thread):
	def __init__(self, manager, timelapseId, timelapseFreq):
		super(TimelapseWorker, self).__init__()

		self._stopExecution = False
		self._cm = manager
		self._resumeFromPause = threading.Event()

		self.daemon = True
		self.timelapseId = timelapseId
		self.timelapseFreq = timelapseFreq

	def run(self):
		lastUpload = 0
		self._resumeFromPause.set()
		while not self._stopExecution:
			if (time.time() - lastUpload) >= self.timelapseFreq and self._cm.addPhotoToTimelapse(self.timelapseId):
				lastUpload = time.time()

			time.sleep(1)
			self._resumeFromPause.wait()

	def stop(self):
		self._stopExecution = True
		if self.isPaused():
			self.resume()
			
		self.join()

	def pause(self):
		self._resumeFromPause.clear()

	def resume(self):
		self._resumeFromPause.set()

	def isPaused(self):
		return not self._resumeFromPause.isSet()

class CameraManager(object):
	def __init__(self):
		self._eventManager = eventManager()

		self.timelapseWorker = None
		self.timelapseInfo = None

		self.videoType = settings().get(["camera", "encoding"])
		self.videoSize = settings().get(["camera", "size"])
		self.videoFramerate = settings().get(["camera", "framerate"])
		self.open_camera()
		

	def shutdown(self):
		self._logger.info('Shutting Down CameraManager')
		self.close_camera()

		if self.timelapseWorker:
			self.timelapseWorker.stop()
			self.timelapseWorker = None

		global _instance
		_instance = None

	def addPhotoToTimelapse(self, timelapseId):
		#Build text
		printerData = printerManager().getCurrentData()
		text = "%d%% - Layer %s%s" % (
			printerData['progress']['completion'], 
			str(printerData['progress']['currentLayer']) if printerData['progress']['currentLayer'] else '--',
			"/%s" % str(printerData['job']['layerCount'] if printerData['job']['layerCount'] else '')
		)

		picBuf = self.get_pic(text=text)

		if picBuf:
			picData = astroprintCloud().uploadImageFile(timelapseId, picBuf)
			#we need to check again as it's possible that this was the last
			#pic and the timelapse is closed.
			if picData and self.timelapseInfo:
				self.timelapseInfo['last_photo'] = picData['url']
				self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)
				return True

		return False

	def start_timelapse(self, freq):
		if freq == '0':
			return False

		if self.timelapseWorker:
			self.stop_timelapse()

		#check that there's a print ongoing otherwise don't start
		selectedFile = printerManager()._selectedFile
		if not selectedFile:
			return False

		if not self.isCameraAvailable():
			if not self.open_camera():
				return False

		timelapseId = astroprintCloud().startPrintCapture(os.path.split(selectedFile["filename"])[1])
		if timelapseId:
			self.timelapseInfo = {
				'id': timelapseId,
				'freq': freq,
				'paused': False,
				'last_photo': None
			}

			if freq == 'layer':
				# send first pic and subscribe to layer change events
				self.addPhotoToTimelapse(timelapseId)
				self._eventManager.subscribe(Events.LAYER_CHANGE, self._onLayerChange)

			else:
				try:
					freq = float(freq)
				except ValueError:
					return False

				self.timelapseInfo['freq'] = freq
				self.timelapseWorker = TimelapseWorker(self, timelapseId, freq)
				self.timelapseWorker.start()

			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)

			return True	

		return False	

	def update_timelapse(self, freq):
		if self.timelapseInfo and self.timelapseInfo['freq'] != freq:
			if freq == 'layer':
				if self.timelapseWorker and not self.timelapseWorker.isPaused():
					self.pause_timelapse();

				# subscribe to layer change events
				self._eventManager.subscribe(Events.LAYER_CHANGE, self._onLayerChange)
			else:
				try:
					freq = float(freq)
				except ValueError:
					return False

				# if subscribed to layer change events, unsubscribe here
				self._eventManager.unsubscribe(Events.LAYER_CHANGE, self._onLayerChange)

				if freq == 0:
					self.pause_timelapse()
				elif not self.timelapseWorker:
					self.timelapseWorker = TimelapseWorker(self, self.timelapseInfo['id'], freq)
					self.timelapseWorker.start()
				elif self.timelapseWorker.isPaused():
					self.timelapseWorker.timelapseFreq = freq
					self.resume_timelapse()
				else:
					self.timelapseWorker.timelapseFreq = freq

			self.timelapseInfo['freq'] = freq
			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)
			
			return True

		return False

	def stop_timelapse(self, takeLastPhoto = False):
		#unsubscribe from layer change events
		self._eventManager.unsubscribe(Events.LAYER_CHANGE, self._onLayerChange)
		self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, None)

		if self.timelapseWorker:
			self.timelapseWorker.stop()
			self.timelapseWorker = None

		if takeLastPhoto and self.timelapseInfo:
			self.addPhotoToTimelapse(self.timelapseInfo['id'])

		self.timelapseInfo = None

		return True

	def pause_timelapse(self):
		if self.timelapseWorker and not self.timelapseWorker.isPaused():
			self.timelapseWorker.pause()
			self.timelapseInfo['paused'] = True
			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)
			return True

		return False

	def resume_timelapse(self):
		if self.timelapseWorker and self.timelapseWorker.isPaused():
			self.timelapseWorker.resume()
			self.timelapseInfo['paused'] = False
			self._eventManager.fire(Events.CAPTURE_INFO_CHANGED, self.timelapseInfo)
			return True

		return False

	def settingsChanged(self, cameraSettings):
		pass

	def open_camera(self):
		return False

	def close_camera(self):
		pass

	def start_video_stream(self):
		pass

	def stop_video_stream(self):
		pass

	def list_camera_info(self):
		pass

	def list_devices(self):
		pass

	def get_pic(self, text=None):
		pass

	def get_pic_async(self, done, text=None):
		pass

	def save_pic(self, filename, text=None):
		pass

	def isCameraAvailable(self):
		
		try:
	
			return os.path.exists("/dev/video" + str(self.number_of_video_device))
			
		except:
			
			return False

	def _get_pixel_formats(self,device, maxformats=5):
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
	            print("Unable to determine Pixel Formats, this may be a "\
	                    "driver issue.")
	        return supported_formats
	    return supported_formats

	def _get_supported_resolutions(self, device):

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

		if '/dev/video' not in str(device):
			device = '/dev/video' + str(device)

		supported_formats = self._get_pixel_formats(device)
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
		            while fcntl.ioctl(vd,v4l2.VIDIOC_ENUM_FRAMESIZES,framesize) == 0:
				if framesize.type == v4l2.V4L2_FRMSIZE_TYPE_DISCRETE:
		                    resolutions.append([framesize.discrete.width,
		                        framesize.discrete.height])
		                # for continuous and stepwise, let's just use min and
		                # max they use the same structure and only return
		                # one result
		                elif framesize.type == v4l2.V4L2_FRMSIZE_TYPE_CONTINUOUS or\
		                     framesize.type == v4l2.V4L2_FRMSIZE_TYPE_STEPWISE:
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
		                print("Unable to determine supported framesizes "\
		                      "(resolutions), this may be a driver issue.")
		                return supported_formats
		    supported_format['resolutions'] = resolutions
		return supported_formats

	def isResolutionSupported(self,resolution):

		supported_formats = self._get_supported_resolutions(self.number_of_video_device)
		
		resolutions = []

		for supported_format in supported_formats:
		    if supported_format.get('pixelformat') == 'YUYV':
		        resolutions = supported_format.get('resolutions')

		arrResolution = resolution.split('x')
		
		resolution = []
		#return [640L,480L] in resolutions
		for element in arrResolution:
			resolution += [long(element)]

		return resolution in resolutions

	## private functions

	def _onLayerChange(self, event, payload):
		if self.timelapseInfo:
			self.addPhotoToTimelapse(self.timelapseInfo['id'])
