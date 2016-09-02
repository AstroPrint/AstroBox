# coding=utf-8
__author__ = "Rafael Luque <rafael@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import gi
import time
import logging
import os
import threading

from octoprint.events import eventManager, Events
from octoprint.settings import settings

try:
	gi.require_version('Gst', '1.0')
except ValueError:
	raise ImportError

from gi.repository import Gst as gst

from astroprint.camera.v4l2 import V4L2Manager
from astroprint.webrtc import webRtcManager

from blinker import signal

gst.init(None)

class GStreamerManager(V4L2Manager):
	name = 'gstreamer'

	def __init__(self, videoDevice):
		self.gstreamerVideo = None
		self.asyncPhotoTaker = None
		self.pipeline = None
		self.initPipeline()
		self._logger = logging.getLogger(__name__)


		super(GStreamerManager, self).__init__(videoDevice)



	def isCameraConnected(self):
		return super(GStreamerManager, self).isCameraConnected() and self.gstreamerVideo is not None

	def open_camera(self):
		if self.gstreamerVideo is None:
			self.reScan(self.cameraInfo)

		return True

	def freeMemory(self):
		self.stop_video_stream()
		webRtcManager().stopJanus()

		if self.gstreamerVideo:
			self.gstreamerVideo.freeMemory()
			self.gstreamerVideo = None

	def reScan(self,cameraInfo=None):
		try:
			isCameraConnected = super(GStreamerManager, self).isCameraConnected()
			tryingTimes = 1

			while not isCameraConnected and tryingTimes < 4:#3 retrying times for searching camera
				self._logger.info('Camera not found... retrying %s times' %tryingTimes)
				isCameraConnected = super(GStreamerManager, self).isCameraConnected()
				time.sleep(1)
				tryingTimes +=1


			if self.gstreamerVideo:
				self.freeMemory()
				self.gstreamerVideo = None
				self.cameraInfo = None
				self.supported_formats = None

			#if at first time Astrobox were turned on without camera, it is
			#necessary to refresh the name
			if not self.cameraInfo or \
			not self.supported_formats:#starting Astrobox without camera and rescan for adding one of them
			#with this line, if you starts Astrobox without camera, it will try to rescan for camera one time
			#plus, but it is necessary for rescaning a camera after that
				if isCameraConnected:
					self.cameraInfo = {"name":self.getCameraName(),"supportedResolutions":self._getSupportedResolutions()}

			if isCameraConnected and self.cameraInfo['supportedResolutions']:
				self.supported_formats = self.cameraInfo['supportedResolutions']

				if settings().get(["camera", "format"]) == 'x-raw':

					if settings().get(["camera", "encoding"]) == 'h264':

						self.gstreamerVideo = GstreamerRawH264(self.number_of_video_device,self.cameraInfo['name'], self.pipeline)

					else:#vp8

						self.gstreamerVideo = GstreamerRawVP8(self.number_of_video_device,self.cameraInfo['name'], self.pipeline)

				else:#X-H264

					self.gstreamerVideo = GstreamerXH264(self.number_of_video_device,self.cameraInfo['name'], self.pipeline)


		except Exception, error:
			self._logger.error(error, exc_info=True)
			self.gstreamerVideo = None

		return not self.gstreamerVideo is None

	def start_video_stream(self):
		if self.gstreamerVideo:
			if not self.isVideoStreaming():
				return self.gstreamerVideo.play_video()
			else:
				return True
		else:
			return False

	def stop_video_stream(self):

		if self.gstreamerVideo and self.gstreamerVideo.streamProcessState == 'PLAYING':

			return self.gstreamerVideo.stop_video()

		else:

			return False

	def settingsChanged(self, cameraSettings):
		super(GStreamerManager, self).settingsChanged(cameraSettings)

		##When a change in settup is saved, the camera must be shouted down
		##(Janus included, of course)

		eventManager().fire(Events.GSTREAMER_EVENT, {
			'message': 'Your camera settings have been changed. Please reload to restart your video.'
		})
		##

		#initialize a new object with the settings changed
		if self.asyncPhotoTaker:
			self.asyncPhotoTaker.stop()
			self.asyncPhotoTaker = None

		self.freeMemory()
		self.open_camera()

	# def list_camera_info(self):
	#    pass

	# def list_devices(self):
	#    pass

	# There are cases where we want the pic to be synchronous
	# so we leave this version too
	def get_pic(self, text=None):
		if self.gstreamerVideo:
			return self.gstreamerVideo.take_photo(text)

		return None

	def get_pic_async(self, done, text=None):
		# This is just a placeholder
		# we need to pass done around and call it with
		# the image info when ready
		if not self.gstreamerVideo:
			done(None)
			return

		if not self.asyncPhotoTaker:
			self.asyncPhotoTaker = AsyncPhotoTaker(self.gstreamerVideo.take_photo)

		self.asyncPhotoTaker.take_photo(done, text)

	# def save_pic(self, filename, text=None):
	#    pass

	def shutdown(self):
		self._logger.info('Shutting Down GstreamerManager')
		self.pipeline.set_state(gst.State.NULL)
		self.pipeline.send_event(gst.Event.new_eos())


	def isVideoStreaming(self):
		return self.gstreamerVideo.getStreamProcessState() == 'PLAYING'

	def getVideoStreamingState(self):
		return self.gstreamerVideo.streamProcessState

	def close_camera(self):
		if self.asyncPhotoTaker:
			self.asyncPhotoTaker.stop()

	def startLocalVideoSession(self, sessionId):
		return webRtcManager().startLocalSession(sessionId)

	def closeLocalVideoSession(self, sessionId):
		return webRtcManager().closeLocalSession(sessionId)

	@property
	def capabilities(self):
		return ['videoStreaming', 'videoformat-' + self._settings['encoding']]

	## From V4L2Manager
	def _broadcastFataError(self, msg):
		self.gstreamerVideo.fatalErrorManage(True, True, msg, False, True)

	@property
	def _desiredSettings(self):
		return {
			'videoEncoding': [
				{'value': 'h264', 'label': 'H.264'},
				{'value': 'vp8', 'label': 'VP8'}
			],
			'frameSizes': [
				{'value': '640x480', 'label': 'Low (640 x 480)'},
				{'value': '1280x720', 'label': 'High (1280 x 720)'}
			],
			'fps': [],
			'cameraOutput': [
				{'value': 'x-raw', 'label': 'Raw Video'},
				{'value': 'x-h264', 'label': 'H.264 Encoded'}
			]
		}

	#Virtual Interface GStreamerEvents

	def fatalError(self):
		self.freeMemory()
		self.setSafeSettings()
		self.reScan()



	def initPipeline(self):
		# ##
		# PIPELINE IS THE MAIN PIPE OF GSTREAMER FOR GET IMAGES
		# FROM A SOURCE
		# ##
		self.pipeline = gst.Pipeline()
		self.bus = None
		#self.loop = None
		self.initGstreamerBus()

	def deinitPipeline(self):
		self.pipeline = None
		self.bus = None
		#self.loop = None


	def initGstreamerBus(self):
		# ##
		# PIPELINE IS THE MAIN PIPE OF GSTREAMER FOR GET IMAGES
		# FROM A SOURCE
		# ##
		self.bus = self.pipeline.get_bus()
		# self.bus.add_signal_watch_full(1)
		self.bus.add_signal_watch()
		self.bus.connect('message', self.bus_message)
		self.bus.set_flushing(True)

	def deinitGstreamerBus(self):
		# self.bus.add_signal_watch_full(1)
		self.bus.remove_signal_watch()
		#self.bus.disconnect('message')

	def bus_message(self, bus, msg):

		t = msg.type

		if t == gst.MessageType.ELEMENT:

			if 'GstMultiFileSink' in msg.src.__class__.__name__:

				if not self.gstreamerVideo.bus_managed:

					self.gstreamerVideo.bus_managed = True

					if self.gstreamerVideo.photoMode == 'NOT_TEXT':

						try:
							self.gstreamerVideo.tee_video_pad_binNotText.add_probe(gst.PadProbeType.BLOCK_DOWNSTREAM, self.video_bin_pad_probe_callback, None)

						except Exception, error:
							self._logger.error("ERROR IN BUS MESSAGE: %s", error)
							self.fatalErrorManage(True, True, None, True, True)

					else:
						try:
							self.gstreamerVideo.tee_video_pad_bin.add_probe(gst.PadProbeType.BLOCK_DOWNSTREAM, self.video_bin_pad_probe_callback, None)

						except Exception, error:
							self._logger.error("ERROR IN BUS MESSAGE: %s", error)
							self.fatalErrorManage(True, True, None, True, True)

		elif t == gst.MessageType.ERROR:

			busError, detail = msg.parse_error()

			self._logger.error("gstreamer bus message error: %s" % busError)

			if self.gstreamerVideo.waitForPhoto:
				self.gstreamerVideo.stopQueueBinNotText()
				self.gstreamerVideo.photoTaken = False
				self.gstreamerVideo.waitForPhoto.set()

			elif 'Internal data flow error.' in str(busError):
				message = str(busError)
				self.fatalErrorManage(True,True,message, True, True)

		#elif t == gst.MessageType.STATE_CHANGED:
		#	pass

		elif t == gst.MessageType.EOS:

			self._logger.info("gstreamer EOS (End of Stream) message received.")

			self.freeMemory()
			self.deinitGstreamerBus()
			self.deinitPipeline()
			gst.deinit()
			webRtcManager().shutdown()


	def video_bin_pad_probe_callback(self, pad, info, user_data):

		if info.id == 1:

			if self.gstreamerVideo.photoMode == 'NOT_TEXT':
			#queuebinNotText
				try:
					self.gstreamerVideo.stopQueueBinNotText()

					self.gstreamerVideo.photoTaken = True

					self.gstreamerVideo.tee_video_pad_binNotText.remove_probe(info.id)

				except Exception, error:

					self._logger.error("ERROR IN VIDEO_BIN_PAD_PROBE_CALLBACK: %s", error)

					if self.gstreamerVideo.streamProcessState == 'TAKING_PHOTO':
						self.gstreamerVideo.queuebinNotText.set_state(gst.State.PAUSED)
						self.gstreamerVideo.queuebinNotText.set_state(gst.State.NULL)

					self.gstreamerVideo.waitForPhoto.set()
					self.fatalErrorManage(True, True, None, True, True)

					return gst.PadProbeReturn.DROP

			else:
				#queuebin
				try:
					self.gstreamerVideo.stopQueueBin()

					self.gstreamerVideo.photoTaken = True

					self.gstreamerVideo.tee_video_pad_bin.remove_probe(info.id)

				except Exception, error:

					self._logger.error("ERROR IN VIDEO_BIN_PAD_PROBE_CALLBACK: %s", error)

					if self.gstreamerVideo.streamProcessState == 'TAKING_PHOTO':
						self.gstreamerVideo.queuebin.set_state(gst.State.PAUSED)
						self.gstreamerVideo.queuebin.set_state(gst.State.NULL)

					self.gstreamerVideo.waitForPhoto.set()
					self.fatalErrorManage(True, True, None, True, True)

					return gst.PadProbeReturn.DROP

			self.gstreamerVideo.waitForPhoto.set()

			return gst.PadProbeReturn.DROP

		else:

			return gst.PadProbeReturn.DROP


	def fatalErrorManage(self, NULLToQueuebinNotText=True, NULLToQueuebin=True, Message=None, SendToLocal=True, SendToRemote=True):

		self.gstreamerVideo.fatalErrorManaged = True

		self._logger.error('Gstreamer fatal error managing')

		if NULLToQueuebinNotText and self.gstreamerVideo.queuebinNotText:
				self.gstreamerVideo.queuebinNotText.set_state(gst.State.PAUSED)
				self.gstreamerVideo.queuebinNotText.set_state(gst.State.NULL)

		#if NULLToQueuebin and self.gstreamerVideo.queuebin:
		#	self.gstreamerVideo.queuebin.set_state(gst.State.PAUSED)
		#	self.gstreamerVideo.queuebin.set_state(gst.State.NULL)

		self.pipeline.set_state(gst.State.PAUSED)
		self.pipeline.set_state(gst.State.NULL)
		#self.reset_pipeline_gstreamer_state()

		if self.gstreamerVideo.waitForPhoto:
			self.gstreamerVideo.stopQueueBinNotText()
			self.photoTaken = False
			self.gstreamerVideo.waitForPhoto.set()

		if SendToRemote:
			#signaling for remote peers
			manage_fatal_error_webrtc = signal('manage_fatal_error_webrtc')
			manage_fatal_error_webrtc.send('cameraError',message=Message)


		if SendToLocal:
			#event for local peers
			eventManager().fire(Events.GSTREAMER_EVENT, {
				'message': Message or 'Fatal error occurred in video streaming'
			})

		try:
			self._logger.error("Trying to get list of formats supported by your camera...")
			import subprocess
			self._logger.error(subprocess.Popen("v4l2-ctl --list-formats-ext", shell=True, stdout=subprocess.PIPE).stdout.read())
		except:
			self._logger.error("Supported formats can not be obtainted...")

		self.fatalError()

class GStreamer(object):

	def __init__(self, device, cameraName, pipeline):

		self._logger = logging.getLogger(__name__)

		try:

			self.videotype = settings().get(["camera", "encoding"])
			self.size = settings().get(["camera", "size"]).split('x')
			self.framerate = settings().get(["camera", "framerate"])
			self.format = settings().get(["camera", "format"])

			self.bus_managed = True
			self.fatalErrorManaged = None
			self.photoTaken = None
			self.waitForPhoto = None

			self.pipeline = pipeline

			self._logger.info("Initializing Gstreamer with camera %s, encoding: %s, size: %s and %s fps in %s format" % (cameraName, self.videotype , settings().get(["camera", "size"]) , str(self.framerate) , self.format))

			# ##
			# IMAGE FOR SAVING PHOTO
			self.tempImage = '/tmp/gstCapture.jpg'

			# STREAM DEFAULT STATE
			self.streamProcessState = 'PAUSED'

			self.photoMode = 'NOT_TEXT'

			#tee

			self.initTeeSource(device)

			self.composeTeeSource()

			self.linkTeeSource()

			#video queue

			self.initQueueRaw()

			self.composeQueueRaw()

			self.linkQueueRaw()

			#photo queue

			self.initQueueBin()

			self.composeQueueBin()

			self.linkQueueBin()

			#photo text queue

			self.initQueueBinNotText()

			self.composeQueueBinNotText()

			self.linkQueueBinNotText()


		except Exception, error:
			self._logger.error("Error initializing GStreamer's video pipeline: %s" % str(error))
			raise error

	def freeMemory(self):

		self.bus_managed = False
		self.fatalErrorManaged = None

		try:

			self.waitForPlayVideo.set()
			self.waitForPlayVideo.clear()

		except: pass

		self.destroyQueueBinNotText()
		self.destroyQueueBin()
		self.destroyQueueRaw()
		self.destroyTeeSource()

	def __del__(self):
		self._logger.info("Gstreamer memory cleaned")

	def initTeeSource(self,device):
		# VIDEO SOURCE DESCRIPTION
		# #DEVICE 0 (FIRST CAMERA) USING v4l2src DRIVER
		# #(v4l2src: VIDEO FOR LINUX TO SOURCE)
		self.video_source = gst.ElementFactory.make('v4l2src', 'video_source')
		self.video_source.set_property("device", '/dev/video' + str(device))

		# ASTROPRINT'S LOGO FROM DOWN RIGHT CORNER
		self.video_logo = gst.ElementFactory.make('gdkpixbufoverlay', 'logo_overlay')
		self.video_logo.set_property('location', '/AstroBox/src/astroprint/static/img/astroprint_logo.png')
		self.video_logo.set_property('overlay-width', 150)
		self.video_logo.set_property('overlay-height', 29)

		self.size = settings().get(["camera", "size"]).split('x')

		self.video_logo.set_property('offset-x', int(self.size[0]) - 160)
		self.video_logo.set_property('offset-y', int(self.size[1]) - 30)

		camera1caps = gst.Caps.from_string('video/x-raw,format=I420,width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate)

		self.src_caps = gst.ElementFactory.make("capsfilter", "filter1")
		self.src_caps.set_property("caps", camera1caps)

		# ##
		# TEE COMMAND IN GSTREAMER ABLES TO JOIN NEW OUTPUT
		# QUEUES TO THE SAME SOURCE
		self.tee = gst.ElementFactory.make('tee', 'tee')
		# ##

	def deInitTeeSource(self):
		self.video_source = None
		self.video_logo = None
		self.src_caps = None
		self.tee = None

	def composeTeeSource(self):
		# SOURCE AND LOGO HAVE TO BE
		# ADDED TO PIPELINE
		self.pipeline.add(self.video_source)
		self.pipeline.add(self.video_logo)
		self.pipeline.add(self.src_caps)
		self.pipeline.add(self.tee)

	def dismantleTeeSource(self):
		self.pipeline.remove(self.tee)
		self.pipeline.remove(self.src_caps)
		self.pipeline.remove(self.video_logo)
		self.pipeline.remove(self.video_source)


	def linkTeeSource(self):
		# ##
		# LINKS MAKE A GSTREAMER LINE, LIKE AN IMAGINE TRAIN
		# WICH WAGONS ARE LINKED IN LINE OR QUEUE
		# ##
		self.video_source.link(self.video_logo)
		self.video_logo.link(self.src_caps)
		self.src_caps.link(self.tee)

	def unlinkTeeSource(self):

		self.src_caps.unlink(self.tee)
		self.video_logo.unlink(self.src_caps)
		self.video_source.unlink(self.video_logo)

	def initQueueRaw(self):
		# ##
		# GSTRAMER MAIN QUEUE: DIRECTLY CONNECTED TO SOURCE
		self.queueraw = gst.ElementFactory.make('queue', None)

		# ##
		# MODE FOR BROADCASTING VIDEO
		self.udpsinkout = gst.ElementFactory.make('udpsink', 'udpsinkvideo')
		self.udpsinkout.set_property('host', '127.0.0.1')
		self.udpsinkout.set_property('port', 8004)
		# ##

		encodeNeedToAdd = True
		self.encode = gst.ElementFactory.make('omxh264enc', None)

		# CAPABILITIES FOR H264 OUTPUT
		self.enc_caps = gst.ElementFactory.make("capsfilter", "filter2")
		self.enc_caps.set_property("caps", gst.Caps.from_string('video/x-h264,profile=high'))

		# VIDEO PAY FOR H264 BEING SHARED IN UDP PACKAGES
		self.videortppay = gst.ElementFactory.make('rtph264pay', 'rtph264pay')
		self.videortppay.set_property('pt', 96)
		self.videortppay.set_property('config-interval', 1)

	def deInitQueueRaw(self):
		self.queueraw = None
		self.encode = None
		self.enc_caps = None
		self.videortppay = None
		self.udpsinkout = None

	def destroyQueueRaw(self):
		self.unlinkQueueRaw()
		self.dismantleQueueRaw()
		self.deInitQueueRaw()

	def composeQueueRaw(self):
		self.pipeline.add(self.queueraw)
		self.pipeline.add(self.encode)
		self.pipeline.add(self.enc_caps)
		self.pipeline.add(self.videortppay)
		self.pipeline.add(self.udpsinkout)

	def dismantleQueueRaw(self):
		self.pipeline.remove(self.udpsinkout)
		self.pipeline.remove(self.videortppay)
		self.pipeline.remove(self.enc_caps)
		self.pipeline.remove(self.encode)
		self.pipeline.remove(self.queueraw)

	def linkQueueRaw(self):
		self.queueraw.link(self.encode)
		self.encode.link(self.enc_caps)
		self.enc_caps.link(self.videortppay)
		self.videortppay.link(self.udpsinkout)

	def unlinkQueueRaw(self):
		self.videortppay.unlink(self.udpsinkout)
		self.enc_caps.unlink(self.videortppay)
		self.encode.unlink(self.enc_caps)
		self.queueraw.unlink(self.encode)

	def padLinkQueueRaw(self):
		# TEE PADDING MANAGING
		# #TEE SOURCE H264
		self.tee_video_pad_video = self.tee.get_request_pad("src_%u")

		# TEE SINKING MANAGING
		# #VIDEO SINK QUEUE
		self.queue_video_pad = self.queueraw.get_static_pad("sink")

		# TEE PAD LINK
		# #VIDEO PADDING
		gst.Pad.link(self.tee_video_pad_video, self.queue_video_pad)

	def padUnLinkQueueRaw(self):
		gst.Pad.unlink(self.tee_video_pad_video, self.queue_video_pad)

	def startQueueRaw(self):

		#self.pipeline.add(self.udpsinkout)

		#self.videortppay.link(self.udpsinkout)

		self.padLinkQueueRaw()

	def stopQueueRaw(self):

		self.padUnLinkQueueRaw()

		#self.videortppay.unlink(self.udpsinkout)

		#self.pipeline.remove(self.udpsinkout)

	def initQueueBin(self):

		self.queuebin = gst.ElementFactory.make('queue', 'queuebin')

		self.multifilesinkphoto = gst.ElementFactory.make('multifilesink', 'multifilesink')
		self.multifilesinkphoto.set_property('location', self.tempImage)
		self.multifilesinkphoto.set_property('max-files', 1)
		self.multifilesinkphoto.set_property('post-messages', True)
		self.multifilesinkphoto.set_property('async', True)

		self.photo_logo = gst.ElementFactory.make('gdkpixbufoverlay', None)
		self.photo_logo.set_property('location', '/AstroBox/src/astroprint/static/img/camera-info-overlay.jpg')
		self.photo_logo.set_property('offset-x', 0)
		self.photo_logo.set_property('offset-y', 0)

		"""
		# PREPARING PHOTO
		# SETTING THE TEXT INFORMATION ABOUT THE PRINTING STATE IN PHOTO
		text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'></span>"
		self.photo_text.set_property('text', text)
		"""

		self.photo_text = gst.ElementFactory.make('textoverlay', None)
		text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>0% - Layer - X / X </span>"
		self.photo_text.set_property('text', text)
		self.photo_text.set_property('valignment', 'top')
		self.photo_text.set_property('ypad', 0)
		self.photo_text.set_property('halignment', 'left')


		if self.size[1] == '720':

			self.photo_logo.set_property('overlay-width',449)
			self.photo_logo.set_property('overlay-height',44)
			self.photo_text.set_property('xpad', 70)

		else:

			self.photo_text.set_property('xpad', 35)


		self.jpegenc = gst.ElementFactory.make('jpegenc', 'jpegenc')
		self.jpegenc.set_property('quality',65)

	def deInitQueueBin(self):
		self.queuebin = None
		self.jpegenc = None
		self.multifilesinkphoto = None

	def composeQueueBin(self):
		self.pipeline.add(self.queuebin)
		self.pipeline.add(self.photo_logo)
		self.pipeline.add(self.photo_text)
		self.pipeline.add(self.jpegenc)

	def dismantleQueueBin(self):
		#self.pipeline.remove(self.multifilesinkphoto)
		self.pipeline.remove(self.photo_text)
		self.pipeline.remove(self.photo_logo)
		self.pipeline.remove(self.jpegenc)
		self.pipeline.remove(self.queuebin)

	def linkQueueBin(self):
		# LINKING PHOTO ELEMENTS (INCLUDED TEXT)
		self.queuebin.link(self.photo_logo)
		self.photo_logo.link(self.photo_text)
		self.photo_text.link(self.jpegenc)

	def unlinkQueueBin(self):
		# LINKING PHOTO ELEMENTS (INCLUDED TEXT)
		self.jpegenc.unlink(self.multifilesinkphoto)
		self.photo_text.link(self.jpegenc)
		self.photo_logo.link(self.photo_text)
		self.queuebin.link(self.photo_logo)

	def destroyQueueBin(self):
		self.unlinkQueueBin()
		self.dismantleQueueBin()
		self.deInitQueueBin()


	def initQueueBinNotText(self):
		self.queuebinNotText = gst.ElementFactory.make('queue', 'queuebinNotText')

		#self.multifilesinkphotoNotTextNeedAdded = True
		self.multifilesinkphotoNotText = gst.ElementFactory.make('multifilesink', 'multifilesinkNotText')
		self.multifilesinkphotoNotText.set_property('location', self.tempImage)
		self.multifilesinkphotoNotText.set_property('max-files', 1)
		self.multifilesinkphotoNotText.set_property('post-messages', True)
		self.multifilesinkphotoNotText.set_property('async', True)

		self.jpegencNotText = gst.ElementFactory.make('jpegenc', 'jpegencNotText')
		self.jpegencNotText.set_property('quality',65)

	def deInitQueueBinNotText(self):
		self.queuebinNotText = None
		self.jpegencNotText = None
		self.multifilesinkphotoNotText = None

	def composeQueueBinNotText(self):
		self.pipeline.add(self.queuebinNotText)
		self.pipeline.add(self.jpegencNotText)
		#self.pipeline.add(self.multifilesinkphotoNotText)

	def dismantleQueueBinNotText(self):
		#self.pipeline.remove(self.multifilesinkphotoNotText)
		self.pipeline.remove(self.jpegencNotText)
		self.pipeline.remove(self.queuebinNotText)


	def linkQueueBinNotText(self):
		# LINKING PHOTO ELEMENTS (WITHOUT TEXT ON PHOTO)
		self.queuebinNotText.link(self.jpegencNotText)
		#self.jpegencNotText.link(self.multifilesinkphotoNotText)

	def unlinkQueueBinNotText(self):
		self.jpegencNotText.unlink(self.multifilesinkphotoNotText)
		self.queuebinNotText.unlink(self.jpegencNotText)

	def destroyQueueBinNotText(self):
		self.unlinkQueueBinNotText()
		self.dismantleQueueBinNotText()
		self.deInitQueueBinNotText()

	def padLinkQueueBinNotText(self):

		self.tee_video_pad_binNotText = self.tee.get_request_pad("src_%u")

		self.queue_videobin_padNotText = self.queuebinNotText.get_static_pad("sink")

		gst.Pad.link(self.tee_video_pad_binNotText, self.queue_videobin_padNotText)


	def padUnLinkQueueBinNotText(self):

		gst.Pad.unlink(self.tee_video_pad_binNotText, self.queue_videobin_padNotText)

	def padLinkQueueBin(self):

		self.tee_video_pad_bin = self.tee.get_request_pad("src_%u")

		self.queue_videobin_pad = self.queuebin.get_static_pad("sink")

		gst.Pad.link(self.tee_video_pad_bin, self.queue_videobin_pad)


	def padUnLinkQueueBin(self):

		gst.Pad.unlink(self.tee_video_pad_bin, self.queue_videobin_pad)


	def startQueueBinNotText(self):
		self.pipeline.add(self.multifilesinkphotoNotText)

		self.jpegencNotText.link(self.multifilesinkphotoNotText)

		self.padLinkQueueBinNotText()

	def stopQueueBinNotText(self):
		#self.padUnLinkQueueBinNotText()
		#self.jpegencNotText.unlink(self.multifilesinkphotoNotText)
		self.pipeline.remove(self.multifilesinkphotoNotText)

	def play_video(self):

		if not self.streamProcessState == 'PREPARING_VIDEO' or not  self.streamProcessState == 'PLAYING':
			# SETS VIDEO ENCODING PARAMETERS AND STARTS VIDEO
			try:
				waitingForVideo = True

				self.waitForPlayVideo = threading.Event()

				while waitingForVideo:
					if self.streamProcessState == 'TAKING_PHOTO' or self.streamProcessState == '':
						waitingForVideo = self.waitForPlayVideo.wait(2)
					else:
						self.waitForPlayVideo.set()
						self.waitForPlayVideo.clear()
						waitingForVideo = False

				self.streamProcessState = 'PREPARING_VIDEO'

				self.startQueueRaw()

				# START PLAYING THE PIPELINE
				self.streamProcessState = 'PLAYING'

				stateChanged = self.pipeline.set_state(gst.State.PLAYING)
				if stateChanged == gst.StateChangeReturn.FAILURE:
					return False


				return True

			except Exception, error:
				self._logger.error("Error playing video with GStreamer: %s" % str(error), exc_info = True)
				self.pipeline.set_state(gst.State.PAUSED)
				self.pipeline.set_state(gst.State.NULL)

				return False

	def stop_video(self):
		# STOPS THE VIDEO
		try:
			if self.streamProcessState == 'TAKING_PHOTO':
				self.queueraw.set_state(gst.State.PAUSED)

			waitingForStopPipeline = True

			self.waitForPlayPipeline = threading.Event()

			while waitingForStopPipeline:
				if self.streamProcessState == 'TAKING_PHOTO' or self.streamProcessState == '':

					waitingForStopPipeline = self.waitForPlayPipeline.wait(2)
				else:

					self.waitForPlayPipeline.set()
					self.waitForPlayPipeline.clear()
					waitingForStopPipeline = False

			self.stopQueueRaw()

			self.pipeline.set_state(gst.State.PAUSED)

			stateChanged = self.pipeline.set_state(gst.State.NULL)

			if stateChanged == gst.StateChangeReturn.FAILURE:
				return False

			self.streamProcessState = 'PAUSED'

			return True

		except Exception, error:

			self._logger.error("Error stopping video with GStreamer: %s" % str(error), exc_info=True)
			self.pipeline.set_state(gst.State.PAUSED)
			self.pipeline.set_state(gst.State.NULL)

			return False



	def destroyTeeSource(self):
		self.unlinkTeeSource()
		self.dismantleTeeSource()
		self.deInitTeeSource()

	def take_photo(self, textPhoto, tryingTimes=0):

			self.waitForPhoto = threading.Event(None)

			if self.streamProcessState == 'PREPARING_VIDEO' or self.streamProcessState == '':

				waitingState = self.waitForPhoto.wait(5)
				self.waitForPhoto.clear()

				# waitingState values:
				#  - True: exit before timeout. The device is able to take photo because video was stablished.
				#  - False: timeout given. The device is busy stablishing video. It is not able to take photo yet.

				if not waitingState:
					return None

			# TAKES A PHOTO USING GSTREAMER
			self.take_photo_and_return(textPhoto)
			# THEN, WHEN PHOTO IS STORED, THIS IS REMOVED PHISICALLY
			# FROM HARD DISK FOR GETTING NEW PHOTOS AND FREEING SPACE

			photo = None

			try:

				self.waitForPhoto.wait(None)
				# waitingState values:
				#  - True: exit before timeout
				#  - False: timeout given


				if self.streamProcessState == 'TAKING_PHOTO':

					self.pipeline.set_state(gst.State.PAUSED)
					self.pipeline.set_state(gst.State.NULL)
					self.streamProcessState = 'PAUSED'

				elif self.streamProcessState == 'TAKING_PHOTO_PLAYING':

					self.streamProcessState = 'PLAYING'

				if self.fatalErrorManaged:
					self.fatalErrorManaged = False
					return None

				if self.photoTaken :#photo write in disk

					try:

						with open(self.tempImage, 'r') as fin:
							photo = fin.read()

						os.unlink(self.tempImage)

					except:
						self._logger.error('Error while opening photo file: recomposing photo maker process...')

				else:#photo error

					if tryingTimes >= 3:

						self._logger.error('Error in Gstreamer: bus does not get a GstMultiFileSink kind of message. Tried %s times, but unluckly It was not possible.' % tryingTimes)

						#signaling for remote peers
						manage_fatal_error_webrtc = signal('manage_fatal_error_webrtc')
						manage_fatal_error_webrtc.send('cameraError',message='Error in Gstreamer: Fatal error: photo queue is not able to be turned on. Gstreamer\'s bus does not get a GstMultiFileSink kind of message')

						#event for local peers
						eventManager().fire(Events.GSTREAMER_EVENT, {
							'message': 'Error in Gstreamer: Fatal error: photo queue is not able to be turned on. Gstreamer\'s bus does not get a GstMultiFileSink kind of message'
						})

						return None


					if not self.bus_managed:

						self._logger.error('Error in Gstreamer: bus does not get a GstMultiFileSink kind of message. Trying again... %s times' % tryingTimes)

						self.bus_managed = True

						if tryingTimes == 2:
							self._logger.error('Error in Gstreamer: Fatal error: photo queue is not able to be turned on. Gstreamer\'s bus does not get a GstMultiFileSink kind of message')

						return self.take_photo(textPhoto,tryingTimes+1)

					else:

						return self.take_photo(textPhoto,tryingTimes+1)

			except Exception, error:

				if self.streamProcessState == 'TAKING_PHOTO':

					self.pipeline.set_state(gst.State.PAUSED)
					self.pipeline.set_state(gst.State.NULL)

					#self.reset_pipeline_gstreamer_state()

				self._logger.error("take_photo except:  %s" % str(error), exc_info = True)
				self.waitForPhoto.clear()

				return None

			self.photoTaken = None

			self.waitForPhoto = None

			return photo

	def take_photo_and_return(self, textPhoto):

		# TAKES A PHOTO USING GSTREAMER
		try:

			try:

				self.pipeline.set_state(gst.State.NULL)

				if textPhoto:

					# PREPARING PHOTO
					# SETTING THE TEXT INFORMATION ABOUT THE PRINTING STATE IN PHOTO
					text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>  " + textPhoto + "  </span>"
					self.photo_text.set_property('text', text)

					self.startQueueBin()

					self.photoMode = 'TEXT'

				else:

					self.startQueueBinNotText()

					self.photoMode = 'NOT_TEXT'

				self.pipeline.set_state(gst.State.PLAYING)


				if self.streamProcessState == 'PLAYING':
					self.streamProcessState = 'TAKING_PHOTO_PLAYING'

				elif self.streamProcessState == 'PAUSED':
					self.streamProcessState = 'TAKING_PHOTO'

			except Exception, error:

				self._logger.error("Error taking photo with GStreamer: %s" % str(error), exc_info = True)
				self.pipeline.set_state(gst.State.PAUSED)
				self.pipeline.set_state(gst.State.NULL)


			self.bus_managed = False

			return None

		except Exception, error:

			self._logger.error("Error taking photo with GStreamer: %s" % str(error), exc_info = True)
			self.pipeline.set_state(gst.State.PAUSED)
			self.pipeline.set_state(gst.State.NULL)

			return None

	def getStreamProcessState(self):
		# RETURNS THE CURRENT STREAM STATE
		return self.streamProcessState

class GstreamerRawH264(GStreamer):
	pass

class GstreamerRawVP8(GStreamer):


	def initQueueRaw(self):
		# ##
		# GSTRAMER MAIN QUEUE: DIRECTLY CONNECTED TO SOURCE
		#if not self.queueraw:
		self.queueraw = gst.ElementFactory.make('queue', None)

		# ##
		# MODE FOR BROADCASTING VIDEO
		#if not self.udpsinkout:
		self.udpsinkout = gst.ElementFactory.make('udpsink', 'udpsinkvideo')
		self.udpsinkout.set_property('host', '127.0.0.1')
		self.udpsinkout.set_property('port', 8005)
		# ##

		#self.encode = None

		#if not self.encode:
		encodeNeedToAdd = True
		self.encode = gst.ElementFactory.make('vp8enc', None)
		self.encode.set_property('target-bitrate', 500000)
		self.encode.set_property('keyframe-max-dist', 500)
		#####VERY IMPORTANT FOR VP8 ENCODING: NEVER USES deadline = 0 (default value)
		self.encode.set_property('deadline', 1)
		#####

		self.videortppay = gst.ElementFactory.make('rtpvp8pay', 'rtpvp8pay')
		self.videortppay.set_property('pt', 96)

	def deInitQueueRaw(self):
		self.queueraw = None
		self.encode = None
		self.videortppay = None
		self.udpsinkout = None

	def composeQueueRaw(self):
		self.pipeline.add(self.queueraw)
		self.pipeline.add(self.encode)
		self.pipeline.add(self.videortppay)
		self.pipeline.add(self.udpsinkout)

	def dismantleQueueRaw(self):
		self.pipeline.remove(self.udpsinkout)
		self.pipeline.remove(self.videortppay)
		self.pipeline.remove(self.encode)
		self.pipeline.remove(self.queueraw)

	def linkQueueRaw(self):
		self.queueraw.link(self.encode)
		self.encode.link(self.videortppay)
		self.videortppay.link(self.udpsinkout)

	def unlinkQueueRaw(self):
		self.videortppay.unlink(self.udpsinkout)
		self.encode.unlink(self.videortppay)
		self.queueraw.unlink(self.encode)


class GstreamerXH264(GStreamer):

	def initTeeSource(self,device):
		# VIDEO SOURCE DESCRIPTION
		# #DEVICE 0 (FIRST CAMERA) USING v4l2src DRIVER
		# #(v4l2src: VIDEO FOR LINUX TO SOURCE)
		self.video_source = gst.ElementFactory.make('v4l2src', 'video_source')
		self.video_source.set_property("device", '/dev/video' + str(device))

		self.size = settings().get(["camera", "size"]).split('x')

		camera1caps = gst.Caps.from_string('video/x-h264,width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate)

		#if not self.src_caps:
		self.src_caps = gst.ElementFactory.make("capsfilter", "filter1")
		self.src_caps.set_property("caps", camera1caps)

		self.h264parse = gst.ElementFactory.make('h264parse',None)

		# ##
		# TEE COMMAND IN GSTREAMER ABLES TO JOIN NEW OUTPUT
		# QUEUES TO THE SAME SOURCE
		#if not self.tee:
		self.tee = gst.ElementFactory.make('tee', 'tee')
		# ##

		self.pipeline.set_state(gst.State.PLAYING)


	def deInitTeeSource(self):
		self.video_source = None
		self.src_caps = None
		self.h264parse = None
		self.tee = None

	def composeTeeSource(self):
		# SOURCE AND LOGO HAVE TO BE
		# ADDED TO PIPELINE
		self.pipeline.add(self.video_source)
		self.pipeline.add(self.src_caps)
		self.pipeline.add(self.h264parse)
		self.pipeline.add(self.tee)

	def dismantleTeeSource(self):
		self.pipeline.remove(self.tee)
		self.pipeline.remove(self.src_caps)
		self.pipeline.remove(self.h264parse)
		self.pipeline.remove(self.video_source)


	def linkTeeSource(self):
		# ##
		# LINKS MAKE A GSTREAMER LINE, LIKE AN IMAGINE TRAIN
		# WICH WAGONS ARE LINKED IN LINE OR QUEUE
		# ##
		self.video_source.link(self.src_caps)
		self.src_caps.link(self.h264parse)
		self.h264parse.link(self.tee)


		self.queuefake = gst.ElementFactory.make('queue', None)


		self.fakesink = gst.ElementFactory.make('fakesink',None)

		self.pipeline.add(self.queuefake)
		self.pipeline.add(self.fakesink)

		self.queuefake.link(self.fakesink)

		self.tee_video_pad_fake = self.tee.get_request_pad("src_%u")

		self.queue_fake_pad = self.queuefake.get_static_pad("sink")

		gst.Pad.link(self.tee_video_pad_fake, self.queue_fake_pad)


	def unlinkTeeSource(self):
		self.h264parse.unlink(self.tee)
		self.src_caps.unlink(self.h264parse)
		self.video_source.unlink(self.src_caps)


	def initQueueRaw(self):
		# ##
		# GSTRAMER MAIN QUEUE: DIRECTLY CONNECTED TO SOURCE
		#if not self.queueraw:
		self.queueraw = gst.ElementFactory.make('queue', None)

		# ##
		# MODE FOR BROADCASTING VIDEO
		#if not self.udpsinkout:
		self.udpsinkout = gst.ElementFactory.make('udpsink', 'udpsinkvideo')
		self.udpsinkout.set_property('host', '127.0.0.1')
		self.udpsinkout.set_property('port', 8004)
		# ##

		#else:

		#	encCapsNeedToAdd = False

		# VIDEO PAY FOR H264 BEING SHARED IN UDP PACKAGES
		#if not self.videortppay:
		self.videortppay = gst.ElementFactory.make('rtph264pay', 'rtph264pay')
		self.videortppay.set_property('pt', 96)
		self.videortppay.set_property('config-interval', 1)

	def deInitQueueRaw(self):
		self.queueraw = None
		self.videortppay = None
		self.udpsinkout = None

	def destroyQueueRaw(self):
		self.unlinkQueueRaw()
		self.dismantleQueueRaw()
		self.deInitQueueRaw()

	def composeQueueRaw(self):
		self.pipeline.add(self.queueraw)
		self.pipeline.add(self.videortppay)
		self.pipeline.add(self.udpsinkout)

	def dismantleQueueRaw(self):
		self.pipeline.remove(self.udpsinkout)
		self.pipeline.remove(self.videortppay)
		self.pipeline.remove(self.queueraw)

	def linkQueueRaw(self):
		self.queueraw.link(self.videortppay)
		self.videortppay.link(self.udpsinkout)

	def unlinkQueueRaw(self):
		self.videortppay.unlink(self.udpsinkout)
		self.queueraw.unlink(self.videortppay)

	def initQueueBinNotText(self):
		self.queuebinNotText = gst.ElementFactory.make('queue', 'queuebinNotText')

		#self.multifilesinkphotoNotTextNeedAdded = True
		self.multifilesinkphotoNotText = gst.ElementFactory.make('multifilesink', 'multifilesinkNotText')
		self.multifilesinkphotoNotText.set_property('location', self.tempImage)
		self.multifilesinkphotoNotText.set_property('max-files', 1)
		self.multifilesinkphotoNotText.set_property('post-messages', True)
		self.multifilesinkphotoNotText.set_property('async', True)

		self.jpegencNotText = gst.ElementFactory.make('jpegenc', 'jpegencNotText')
		self.jpegencNotText.set_property('quality',65)

		self.x264decNotText = gst.ElementFactory.make('omxh264dec',None)

	def deInitQueueBinNotText(self):
		self.queuebinNotText = None
		self.x264decNotText = None
		self.jpegencNotText = None
		self.multifilesinkphotoNotText = None

	def composeQueueBinNotText(self):
		self.pipeline.add(self.queuebinNotText)
		self.pipeline.add(self.x264decNotText)
		self.pipeline.add(self.jpegencNotText)
		#self.pipeline.add(self.multifilesinkphotoNotText)

	def dismantleQueueBinNotText(self):
		#self.pipeline.remove(self.multifilesinkphotoNotText)
		self.pipeline.remove(self.jpegencNotText)
		self.pipeline.remove(self.x264decNotText)
		self.pipeline.remove(self.queuebinNotText)


	def linkQueueBinNotText(self):
		# LINKING PHOTO ELEMENTS (WITHOUT TEXT ON PHOTO)
		self.queuebinNotText.link(self.x264decNotText)
		self.x264decNotText.link(self.jpegencNotText)
		#self.jpegencNotText.link(self.multifilesinkphotoNotText)

	def unlinkQueueBinNotText(self):
		#self.jpegencNotText.unlink(self.multifilesinkphotoNotText)
		self.x264decNotText.unlink(self.jpegencNotText)
		self.queuebinNotText.unlink(self.x264decNotText)

	def startQueueBinNotText(self):
		self.pipeline.add(self.multifilesinkphotoNotText)

		self.jpegencNotText.link(self.multifilesinkphotoNotText)

		self.padLinkQueueBinNotText()

		if self.streamProcessState == 'PAUSED':
			self.videortppay.unlink(self.udpsinkout)
			self.pipeline.remove(self.udpsinkout)

		self.pipeline.set_state(gst.State.PLAYING)

	def stopQueueBinNotText(self):

		if self.streamProcessState == 'TAKING_PHOTO':
			self.padUnLinkQueueBinNotText()
			self.pipeline.add(self.udpsinkout)
			self.videortppay.link(self.udpsinkout)
			self.pipeline.set_state(gst.State.PAUSED)

		self.padUnLinkQueueBinNotText()
		self.jpegencNotText.unlink(self.multifilesinkphotoNotText)
		self.pipeline.remove(self.multifilesinkphotoNotText)

		#ERROR 13!!!!!
		#if self.streamProcessState == 'PLAYING' or self.streamProcessState == 'TAKING_PHOTO_PLAYING':
		#	self.stop_video()
		#	self.play_video()


	def initQueueBin(self):
		self.queuebin = gst.ElementFactory.make('queue', 'queuebin')

		#self.multifilesinkphotoNeedAdded = True
		self.multifilesinkphoto = gst.ElementFactory.make('multifilesink', 'multifilesink')
		self.multifilesinkphoto.set_property('location', self.tempImage)
		self.multifilesinkphoto.set_property('max-files', 1)
		self.multifilesinkphoto.set_property('post-messages', True)
		self.multifilesinkphoto.set_property('async', True)

		self.photo_logo = gst.ElementFactory.make('gdkpixbufoverlay', None)
		self.photo_logo.set_property('location', '/AstroBox/src/astroprint/static/img/camera-info-overlay.jpg')
		self.photo_logo.set_property('offset-x', 0)
		self.photo_logo.set_property('offset-y', 0)

		# ASTROPRINT'S LOGO FROM DOWN RIGHT CORNER
		self.video_logo = gst.ElementFactory.make('gdkpixbufoverlay', 'logo_overlay')
		self.video_logo.set_property('location', '/AstroBox/src/astroprint/static/img/astroprint_logo.png')
		self.video_logo.set_property('overlay-width', 150)
		self.video_logo.set_property('overlay-height', 29)

		self.size = settings().get(["camera", "size"]).split('x')

		self.video_logo.set_property('offset-x', int(self.size[0]) - 160)
		self.video_logo.set_property('offset-y', int(self.size[1]) - 30)

		self.photo_text = gst.ElementFactory.make('textoverlay', None)
		text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>0% - Layer - X / X </span>"
		self.photo_text.set_property('text', text)
		self.photo_text.set_property('valignment', 'top')
		self.photo_text.set_property('ypad', 0)
		self.photo_text.set_property('halignment', 'left')


		if self.size[1] == '720':

			self.photo_logo.set_property('overlay-width',449)
			self.photo_logo.set_property('overlay-height',44)
			self.photo_text.set_property('xpad', 70)

		else:

			self.photo_text.set_property('xpad', 35)

		self.jpegenc = gst.ElementFactory.make('jpegenc', 'jpegenc')
		self.jpegenc.set_property('quality',65)

		self.x264dec = gst.ElementFactory.make('omxh264dec',None)


	def deInitQueueBin(self):
		self.queuebin = None
		self.x264dec = None
		self.photo_text = None
		self.photo_logo = None
		self.video_logo = None
		self.jpegenc = None
		self.multifilesinkphoto = None

	def composeQueueBin(self):
		self.pipeline.add(self.queuebin)
		self.pipeline.add(self.x264dec)
		self.pipeline.add(self.video_logo)
		self.pipeline.add(self.photo_text)
		self.pipeline.add(self.photo_logo)
		self.pipeline.add(self.jpegenc)
		#self.pipeline.add(self.multifilesinkphoto)

	def dismantleQueueBin(self):
		#self.pipeline.remove(self.multifilesinkphoto)
		self.pipeline.remove(self.jpegenc)
		self.pipeline.remove(self.x264dec)
		self.pipeline.remove(self.video_logo)
		self.pipeline.remove(self.photo_text)
		self.pipeline.remove(self.photo_logo)
		self.pipeline.remove(self.queuebin)

	def linkQueueBin(self):
		# LINKING PHOTO ELEMENTS (WITHOUT TEXT ON PHOTO)
		self.queuebin.link(self.x264dec)
		self.x264dec.link(self.video_logo)
		self.video_logo.link(self.photo_logo)
		self.photo_logo.link(self.photo_text)
		self.photo_text.link(self.jpegenc)
		#self.jpegenc.link(self.multifilesinkphoto)

	def unlinkQueueBin(self):
		#self.jpegenc.unlink(self.multifilesinkphoto)
		self.photo_text.unlink(self.jpegenc)
		self.photo_logo.unlink(self.photo_text)
		self.video_logo.unlink(self.photo_logo)
		self.x264dec.unlink(self.video_logo)
		self.queuebin.unlink(self.x264dec)

	def startQueueBin(self):
		self.pipeline.add(self.multifilesinkphoto)

		self.jpegenc.link(self.multifilesinkphoto)

		self.padLinkQueueBin()

		if self.streamProcessState == 'PAUSED':
			self.videortppay.unlink(self.udpsinkout)
			self.pipeline.remove(self.udpsinkout)

		self.pipeline.set_state(gst.State.PLAYING)

	def stopQueueBin(self):

		if self.streamProcessState == 'TAKING_PHOTO':
			self.padUnLinkQueueBin()
			self.pipeline.add(self.udpsinkout)
			self.videortppay.link(self.udpsinkout)
			self.pipeline.set_state(gst.State.PAUSED)

		self.padUnLinkQueueBin()
		self.jpegenc.unlink(self.multifilesinkphoto)
		self.pipeline.remove(self.multifilesinkphoto)


class AsyncPhotoTaker(threading.Thread):
	def __init__(self, take_photo_function):

		super(AsyncPhotoTaker, self).__init__()

		self.threadAlive = True

		self.take_photo_function = take_photo_function

		self.sem = threading.Semaphore(0)
		self.doneFunc = None
		self.text = None
		self.start()

	def run(self):
		while self.threadAlive:
			self.sem.acquire()
			if not self.threadAlive:
				return

			if self.doneFunc:
				self.doneFunc(self.take_photo_function(self.text))
				self.doneFunc = None
				self.text = None

	def take_photo(self, done, text):
		self.doneFunc = done
		self.text = text
		self.sem.release()

	def stop(self):
		self.threadAlive = False
		self.sem.release()

