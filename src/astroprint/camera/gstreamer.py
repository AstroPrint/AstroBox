# coding=utf-8
__author__ = "Rafael Luque <rafael@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import gi
import time
import logging
import os
import threading

from octoprint.settings import settings

gi.require_version('Gst', '1.0')
from gi.repository import GObject as gobject
from gi.repository import Gst as gst

from astroprint.camera import CameraManager
from astroprint.webrtc import webRtcManager

from blinker import signal

gobject.threads_init()
gst.init(None)

class GStreamerManager(CameraManager):
	def __init__(self, number_of_video_device):
		self.number_of_video_device = number_of_video_device
		self.gstreamerVideo = None
		self._logger = logging.getLogger(__name__)
		super(GStreamerManager, self).__init__()

	def open_camera(self):
		try:
			if self.gstreamerVideo is None:
				self.gstreamerVideo = GStreamer(self.number_of_video_device)

		except Exception, error:
			self._logger.error(error)
			self.gstreamerVideo = None

		return self.gstreamerVideo is not None

	def start_video_stream(self):
		if self.gstreamerVideo:
			if not self.isVideoStreaming():
				return self.gstreamerVideo.play_video()
			else:
				return True
		else:
			return False

	def stop_video_stream(self):
		return self.gstreamerVideo.stop_video()

	def settingsChanged(self, cameraSettings):
		pass

	# def list_camera_info(self):
	#    pass

	# def list_devices(self):
	#    pass

	def get_pic(self, text=None):
		self._logger.info("GET_PIC")
		if self.gstreamerVideo:
			self._logger.info("GET_PIC INSIDE IF")
			return self.gstreamerVideo.take_photo(text)

		return None
		
	# def save_pic(self, filename, text=None):
	#    pass

	def isCameraAvailable(self):
		parentCameraAvailable = super(GStreamerManager, self).isCameraAvailable()

		return self.gstreamerVideo is not None and parentCameraAvailable

	def isVideoStreaming(self):
		return self.gstreamerVideo.getStreamProcessState() == 'PLAYING'

	def getVideoStreamingState(self):
		return self.gstreamerVideo.streamProcessState

class GStreamer(object):
	
	# #THIS OBJECT COMPOSE A GSTREAMER LAUNCH LINE
	# IT ABLES FOR DEVELOPPERS TO MANAGE, WITH GSTREAMER,
	# THE PRINTER'S CAMERA: GET PHOTO AND VIDEO FROM IT
	def __init__(self, device):
		
		self._logger = logging.getLogger(__name__)

		try:
			self._logger.info("INIT")

			self.pipeline = None
			self.bus = None
			self.loop = None
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
			# ##
			# CONFIGURATION FOR TAKING PHOTOS
			####
			# LOGO AND WHITE BAR FROM TOP LEFT CORNER THAT APPEARS 
			# IN THE VIDEO COMPOSED BY PHOTOS TAKEN WHILE PRINTING    
			####
			self.photo_logo = gst.ElementFactory.make('gdkpixbufoverlay', None)
			self.photo_logo.set_property('location', '/AstroBox/src/astroprint/static/img/camera-info-overlay.jpg')
			self.photo_logo.set_property('offset-x', 0)
			self.photo_logo.set_property('offset-y', 0)
			####
			# TEXT THAT APPEARS ON WHITE BAR WITH PERCENT PRINTING STATE INFO
			####
			self.photo_text = gst.ElementFactory.make('textoverlay', None)
			text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>0% - Layer - X / X </span>"
			self.photo_text.set_property('text', text)
			self.photo_text.set_property('valignment', 'top')
			self.photo_text.set_property('ypad', 0)
			self.photo_text.set_property('halignment', 'left')
			self.photo_text.set_property('xpad', 35)

			# photo without text
			####
			# SCALING COMMANDS TO SCALE VIDEO SOURCE FOR GETTING PHOTOS ALWAYS WITH
			# THE SAME SIZE
			camerajpegcaps = gst.Caps.from_string('video/x-raw,width=640,height=480,framerate=15/1')
			# camerajpegcaps = gst.Caps.from_string('image/jpeg,framerate=30/1,width=640,height=480')
			self.jpeg_capsNotText = gst.ElementFactory.make("capsfilter", "filterjpegNotText")
			self.jpeg_capsNotText.set_property("caps", camerajpegcaps)
			# ##
			# JPEG ENCODING COMMAND
			# ##
			self.jpegencNotText = gst.ElementFactory.make('jpegenc', 'jpegencNotText')
			self.multifilesinkphotoNotText = None
			#####################

			# photo with text
			####
			# SCALING COMMANDS TO SCALE VIDEO SOURCE FOR GETTING PHOTOS ALWAYS WITH
			# THE SAME SIZE
			self.jpeg_caps = gst.ElementFactory.make("capsfilter", "filterjpeg")
			self.jpeg_caps.set_property("caps", camerajpegcaps)
			# ##
			# JPEG ENCODING COMMAND
			# ##
			self.jpegenc = gst.ElementFactory.make('jpegenc', 'jpegenc')
			self.multifilesinkphoto = None
			#####################


			# ##
			# IMAGE FOR SAVING PHOTO
			self.tempImage = '/tmp/gstCapture.jpg'
			
			# STREAM DEFAULT STATE
			self.streamProcessState = 'PAUSED'
			
			self.photoMode = 'NOT_TEXT'

			self.reset_pipeline_gstreamer_state()
								
		except Exception, error:
			self._logger.error("Error initializing GStreamer's video pipeline: %s" % str(error))
			raise error


	def reset_pipeline_gstreamer_state(self):
		# SETS DEFAULT STATE FOR GSTREAMER OBJECT

		try:
			self._logger.info("RESET PIPELINE")
			# ##
			# GET VIDEO PARAMS CONFIGURATED IN ASTROBOX SETTINGS
			self.videotype = settings().get(["camera", "encoding"])
			self.size = settings().get(["camera", "size"]).split('x')
			self.framerate = settings().get(["camera", "framerate"])
			# ##

			# ##
			# CAPS FOR GETTING IMAGES FROM VIDEO SOURCE
			self.video_logo.set_property('offset-x', int(self.size[0]) - 160)
			self.video_logo.set_property('offset-y', int(self.size[1]) - 30)
			# camera1caps = gst.Caps.from_string('video/x-raw,width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate + '/1')
			camera1caps = gst.Caps.from_string('video/x-raw,format=I420,width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate + '/1')
			self.src_caps = gst.ElementFactory.make("capsfilter", "filter1")
			self.src_caps.set_property("caps", camera1caps)
			# ##

			# ##
			# TEE COMMAND IN GSTREAMER ABLES TO JOIN NEW OUTPUT
			# QUEUES TO THE SAME SOURCE 
			self.tee = gst.ElementFactory.make('tee', 'tee')
			# ##
			
			# ##
			# PIPELINE IS THE MAIN PIPE OF GSTREAMER FOR GET IMAGES
			# FROM A SOURCE
			# ##
			self.pipeline = gst.Pipeline()
			self.bus = self.pipeline.get_bus()
			self.pipeline.set_property('name', 'tee-pipeline')
			# self.bus.add_signal_watch_full(1)
			self.bus.add_signal_watch()
			self.bus.connect('message', self.bus_message)			
			# SOURCE, CONVERSIONS AND OUTPUTS (QUEUES) HAVE TO BE
			# ADDED TO PIPELINE
			self.pipeline.add(self.video_source)
			self.pipeline.add(self.video_logo)
			self.pipeline.add(self.src_caps)
			self.pipeline.add(self.tee)
			# ##
		   
			# ##
			# LINKS MAKE A GSTREAMER LINE, LIKE AN IMAGINE TRAIN
			# WICH WAGONS ARE LINKED IN LINE OR QUEUE
			# ##
			self.video_source.link(self.video_logo)
			self.video_logo.link(self.src_caps)
			self.src_caps.link(self.tee)
			# ##
			
			# ##
			# OBJECTS FOR GETTING IMAGES FROM VIDEO SOURCE IN BINARY,
			# USED FOR GET PHOTOS
			# ##
			self.queuebin = None
			self.tee_video_pad_bin = None        
			self.queue_videobin_pad = None
			self.queuebinNotText = None
			self.tee_video_pad_binNotText = None        
			self.queue_videobin_padNotText = None
			# ##
			
			self.streamProcessState = 'PAUSED'

			self.photoMode = 'NOT_TEXT'

			return True
		
		except Exception, error:
			self._logger.error("Error resetting GStreamer's video pipeline: %s" % str(error))
			if self.pipeline:
				self.pipeline.set_state(gst.State.PAUSED)
				self.pipeline.set_state(gst.State.NULL)
			
			return False
		
	def play_video(self):
		# SETS VIDEO ENCODING PARAMETERS AND STARTS VIDEO
		try:
			self._logger.info("PLAY_VIDEO")

			self.streamProcessState = 'PREPARING_VIDEO'
			# ##
			# GET VIDEO PARAMS CONFIGURATED IN ASTROBOX SETTINGS          
			self.videotype = settings().get(["camera", "encoding"])
			self.size = settings().get(["camera", "size"]).split('x')
			self.frameratee = settings().get(["camera", "framerate"])
			# ##
			
			# ##
			# SETS ASTROPRINT'S LOGO IN VIDEO DEPENDING THE SIZE OF IT
			self.video_logo.set_property('offset-x', int(self.size[0]) - 160)
			self.video_logo.set_property('offset-y', int(self.size[1]) - 30)
			camera1caps = gst.Caps.from_string('video/x-raw,width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate + '/1')
			self.src_caps = gst.ElementFactory.make("capsfilter", "filter1")
			self.src_caps.set_property("caps", camera1caps)
			# ##
				   
			# ##
			# GSTRAMER MAIN QUEUE: DIRECTLY CONNECTED TO SOURCE
			queueraw = gst.ElementFactory.make('queue', 'queueraw')
			# ##
			
			# ##
			# MODE FOR BROADCASTING VIDEO
			udpsinkout = gst.ElementFactory.make('udpsink', 'udpsinkvideo')
			udpsinkout.set_property('host', '127.0.0.1')
			# ##
	
			if self.videotype == 'h264':
				# ##
				# H264 VIDEO MODE SETUP
				# ##
				# ENCODING
				encode = gst.ElementFactory.make('omxh264enc', None)
				# CAPABILITIES FOR H264 OUTPUT
				camera1capsout = gst.Caps.from_string('video/x-h264,profile=high')
				enc_caps = gst.ElementFactory.make("capsfilter", "filter2")
				enc_caps.set_property("caps", camera1capsout)
				# VIDEO PAY FOR H264 BEING SHARED IN UDP PACKAGES
				videortppay = gst.ElementFactory.make('rtph264pay', 'rtph264pay')
				videortppay.set_property('pt', 96)
				# UDP PORT FOR SHARING H264 VIDEO
				udpsinkout.set_property('port', 8004)
				# ##
				
			elif self.videotype == 'vp8':
				# ##
				# VP8 VIDEO MODE STUP
				# ##
				# ENCODING
				encode = gst.ElementFactory.make('vp8enc', None)
				encode.set_property('target-bitrate', 500000)
				encode.set_property('keyframe-max-dist', 500)
				#####VERY IMPORTANT FOR VP8 ENCODING: NEVER USES deadline = 0 (default value)
				encode.set_property('deadline', 1)
				#####
				# VIDEO PAY FOR VP8 BEING SHARED IN UDP PACKAGES                
				videortppay = gst.ElementFactory.make('rtpvp8pay', 'rtpvp8pay')
				videortppay.set_property('pt', 96)
				# UDP PORT FOR SHARING VP8 VIDEO
				udpsinkout.set_property('port', 8005)
				# ##
			
			# ##
			# ADDING VIDEO ELEMENTS TO PIPELINE
			self.pipeline.add(queueraw)
			self.pipeline.add(encode)
			
			if self.videotype == 'h264':
				self.pipeline.add(enc_caps)

			self.pipeline.add(videortppay)
			self.pipeline.add(udpsinkout)
			
			# ADDING PHOTO ELEMENTS TO PIPELINE
			# self.pipeline.add(self.photo_logo)
			# self.pipeline.add(self.photo_text)
			# self.pipeline.add(self.videoscalejpeg)
			# self.pipeline.add(self.jpeg_caps)
			# self.pipeline.add(self.jpegenc)
			# self.pipeline.add(self.videoconvertjpeg)
			# self.pipeline.add(self.videoratejpeg)
			####
			
			# ##
			# LINKING VIDEO ELEMENTS
			self.video_source.link(self.video_logo)
			self.video_logo.link(self.src_caps)
			self.src_caps.link(self.tee)

			queueraw.link(encode)
			
			if self.videotype == 'h264':
				encode.link(enc_caps)
				enc_caps.link(videortppay)
			else:
				encode.link(videortppay)
				
			videortppay.link(udpsinkout)
			
			# #queue for photo without text
			# textPhoto = None

			# CONFIGURATION FOR TAKING SOME FILES (PHOTO) FOR GETTING
			# A GOOD IMAGE FROM CAMERA
			self.multifilesinkphotoNotText = gst.ElementFactory.make('multifilesink', None)
			self.multifilesinkphotoNotText.set_property('location', self.tempImage)
			self.multifilesinkphotoNotText.set_property('max-files', 1)
			self.multifilesinkphotoNotText.set_property('post-messages', True)
			# IF VIDEO IS PLAYING, IT HAS TO TAKE PHOTO USING ANOTHER INTRUCTION            
			self._logger.info("VIDEO IS PLAYING")


			"""#QUEUE FOR TAKING PHOTOS    
			#self.queuebin = gst.ElemCentFactory.make('queue','queuebin')
			#self.queuebinNotText = gst.ElementFactory.make('queue','queuebinNotText')
			###

			#ADDING PHOTO QUEUE TO PIPELINE
			self.pipeline.add(self.queuebin)
			self.pipeline.add(self.jpeg_caps)
			self.pipeline.add(self.jpegenc)
			#ADDING PHOTO QUEUE (without text) TO PIPELINE
			self.pipeline.add(self.queuebinNotText)
			self.pipeline.add(self.photo_logo)
			self.pipeline.add(self.photo_text)
			self.pipeline.add(self.jpeg_capsNotText)
			self.pipeline.add(self.jpegencNotText)
			"""
			# #
			####self.pipeline.add(self.multifilesinkphoto)

			# #TEE SOURCE PHOTO
			# self.tee_video_pad_bin = self.tee.get_request_pad("src_%u")

			# #PHOTO SINK QUEUE
			# self.queue_videobin_pad = self.queuebin.get_static_pad("sink")
			
			# PREPARING PHOTO
			# SETTING THE TEXT INFORMATION ABOUT THE PRINTING STATE IN PHOTO
			"""text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>" + textPhoto + "</span>"
			self.photo_text.set_property('text',text)
			#LINKING PHOTO ELEMENTS (INCLUDED TEXT)
			self.queuebinNotText.link(self.jpeg_capsNotText)
			self.jpeg_capsNotText.link(self.photo_logo)
			self.photo_logo.link(self.photo_text)
			self.photo_text.link(self.jpegencNotText)
			#LINKING PHOTO ELEMENTS (WITHOUT TEXT ON PHOTO)
			self.queuebin.link(self.jpeg_caps)
			self.jpeg_caps.link(self.jpegenc)
			##########
			"""
			# CONFIGURATION FOR TAKING SOME FILES (PHOTO) FOR GETTING
			# A GOOD IMAGE FROM CAMERA
			self.multifilesinkphoto = gst.ElementFactory.make('multifilesink', 'multifilesink')
			self.multifilesinkphoto.set_property('location', self.tempImage)
			self.multifilesinkphoto.set_property('max-files', 1)
			self.multifilesinkphoto.set_property('post-messages', True)
			self.multifilesinkphotoNotText = gst.ElementFactory.make('multifilesink', 'multifilesinkNotText')
			self.multifilesinkphotoNotText.set_property('location', self.tempImage)
			self.multifilesinkphotoNotText.set_property('max-files', 1)
			self.multifilesinkphotoNotText.set_property('post-messages', True)
			# IF VIDEO IS PLAYING, IT HAS TO TAKE PHOTO USING ANOTHER INTRUCTION            
			self._logger.info("VIDEO IS PLAYING")


			# QUEUE FOR TAKING PHOTOS    
			self.queuebin = gst.ElementFactory.make('queue', 'queuebin')
			# ##
			# QUEUE FOR TAKING PHOTOS (without text)
			self.queuebinNotText = gst.ElementFactory.make('queue', 'queuebinNotText')
			# ##

			# ADDING PHOTO QUEUE TO PIPELINE
			self.pipeline.add(self.queuebin)
			self.pipeline.add(self.jpeg_caps)
			self.pipeline.add(self.jpegenc)
			# ADDING PHOTO QUEUE (without text) TO PIPELINE
			self.pipeline.add(self.queuebinNotText)
			self.pipeline.add(self.photo_logo)
			self.pipeline.add(self.photo_text)
			self.pipeline.add(self.jpeg_capsNotText)
			self.pipeline.add(self.jpegencNotText)
			# #

			####self.pipeline.add(self.multifilesinkphoto)

			# #TEE SOURCE PHOTO
			# self.tee_video_pad_bin = self.tee.get_request_pad("src_%u")

			# #PHOTO SINK QUEUE
			# self.queue_videobin_pad = self.queuebin.get_static_pad("sink")

			# PREPARING PHOTO
			# SETTING THE TEXT INFORMATION ABOUT THE PRINTING STATE IN PHOTO
			text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'></span>"
			self.photo_text.set_property('text', text)
			# LINKING PHOTO ELEMENTS (INCLUDED TEXT)
			self.queuebin.link(self.jpeg_caps)
			self.jpeg_caps.link(self.photo_logo)
			self.photo_logo.link(self.photo_text)
			self.photo_text.link(self.jpegenc)
			# LINKING PHOTO ELEMENTS (WITHOUT TEXT ON PHOTO)
			self.queuebinNotText.link(self.jpeg_capsNotText)
			self.jpeg_capsNotText.link(self.jpegencNotText)
			##########
			
			####self.jpegenc.link(self.multifilesinkphoto)	
			# TEE PADDING MANAGING
			# #TEE SOURCE H264
			tee_video_pad_video = self.tee.get_request_pad("src_%u")
			
			# TEE SINKING MANAGING
			# #VIDEO SINK QUEUE
			queue_video_pad = queueraw.get_static_pad("sink")
	
			# TEE PAD LINK
			# #VIDEO PADDING        
			print gst.Pad.link(tee_video_pad_video, queue_video_pad)
			  
			# START PLAYING THE PIPELINE
			self.streamProcessState = 'PLAYING'
			self.pipeline.set_state(gst.State.PLAYING)
			

			self._logger.info("PLAYING")
			# self.loop = gobject.MainLoop()
			# print self.loop
			# self.loop.run()

			self.pipeline.add(self.multifilesinkphotoNotText)
			self.jpegencNotText.link(self.multifilesinkphotoNotText)
			
			self.pipeline.add(self.multifilesinkphoto)
			self.jpegenc.link(self.multifilesinkphoto)

			"""self.tee_video_pad_bin = self.tee.get_request_pad("src_%u")
			self.queue_videobin_pad = self.queuebin.get_static_pad("sink")	

			print gst.Pad.link(self.tee_video_pad_bin,self.queue_videobin_pad)
			
			print self.queuebin.set_state(gst.State.PLAYING)	
			"""

			return True
			
		except Exception, error:
			
			self._logger.info("PLAY VIDEO EXCEPTION")

			self._logger.error("Error playing video with GStreamer: %s" % str(error))
			self.pipeline.set_state(gst.State.PAUSED)
			self.pipeline.set_state(gst.State.NULL)
			self.reset_pipeline_gstreamer_state()
			
			return False

	def stop_video(self):
		# STOPS THE VIDEO
		try:
			while self.streamProcessState == 'TAKING_PHOTO':
				time.sleep(0.1)

			if self.streamProcessState == 'PLAYING':
				self.pipeline.set_state(gst.State.NULL)
				self.reset_pipeline_gstreamer_state()
				self.streamProcessState = 'PAUSED'

			return True
				
		except Exception, error:
			
			self._logger.error("Error stopping video with GStreamer: %s" % str(error))
			self.pipeline.set_state(gst.State.PAUSED)
			self.pipeline.set_state(gst.State.NULL)
			self.reset_pipeline_gstreamer_state()
			
			return False

	def bus_message(self, bus, msg):
		t = msg.type
		# print msg
		# print t
		if t == gst.MessageType.ELEMENT:
			# print msg
			# print msg.type
			# print msg.src
			if 'GstMultiFileSink' in msg.src.__class__.__name__: 

					self._logger.info("VIDEO_BIN_PAD_PROBE_CALLBACK GstMultiFileSink")

					self._logger.info("image got")


					if self.photoMode == 'NOT_TEXT':
						try:
							# ##text in photo
							# self.queuebinNotText.set_state(gst.State.PAUSED)
							self.queuebinNotText.set_state(gst.State.NULL)
							# global info_id
							# #add probe for the source waiting for finish the source data flow
							self.tee_video_pad_binNotText.add_probe(gst.PadProbeType.BLOCK_DOWNSTREAM, self.video_bin_pad_probe_callback, None)
						except Exception, error:
							self._logger.info("ERROR IN BUS MESSAGE: %s", error)
							self.fatalErrorManage(True, True)
						
					else:
						try:
							# self.queuebin.set_state(gst.State.PAUSED)
							self.queuebin.set_state(gst.State.NULL)
							# global info_id
							# #add probe for the source waiting for finish the source data flow
							self.tee_video_pad_bin.add_probe(gst.PadProbeType.BLOCK_DOWNSTREAM, self.video_bin_pad_probe_callback, None)
	
						except Exception, error:
							self._logger.info("ERROR IN BUS MESSAGE: %s", error)
							self.fatalErrorManage(True, True)

					self._logger.info("VIDEO_BIN_PAD_PROBE_CALLBACK GstMultiFileSink END")


		elif t == gst.MessageType.ERROR:
			busError = msg.parse_error()
			self._logger.error("gstreamer bus message error (%s): %s" % busError)
			print self.pipeline.set_state(gst.State.PAUSED)
			print self.pipeline.set_state(gst.State.NULL)

	def video_bin_pad_probe_callback(self, pad, info, user_data):
	
		self._logger.info("VIDEO_BIN_PAD_PROBE_CALLBACK")

		if self.photoMode == 'NOT_TEXT':
			try:
				print pad
				print user_data
				gst.Pad.unlink(self.tee_video_pad_binNotText, self.queue_videobin_padNotText)
				self._logger.info("info: %s", str(info.id))

				self.tee_video_pad_binNotText.remove_probe(info.id)
				

				print self.streamProcessState
				if self.streamProcessState == 'TAKING_PHOTO':
					# self._logger.info("ENTRA'			
					print self.queuebinNotText.set_state(gst.State.PAUSED)
					print self.queuebinNotText.set_state(gst.State.NULL)

					# print self.pipeline.set_state(gst.State.PAUSED)
					# print self.pipeline.set_state(gst.State.NULL)
				
					# self.pipeline.set_state(gst.State.NULL)
					# self.reset_pipeline_gstreamer_state()
					# self.streamProcessState = 'PAUSED'
			except:
				self._logger.info("ERROR IN VIDEO_BIN_PAD_PROBE_CALLBACK: %s", error)
				if self.streamProcessState == 'TAKING_PHOTO':
					# self._logger.info("ENTRA'			
					print self.queuebinNotText.set_state(gst.State.PAUSED)
					print self.queuebinNotText.set_state(gst.State.NULL)
				self.waitForPhoto.set()
				self.fatalErrorManage(True, True)
				return gst.PadProbeReturn.DROP

		else:

			try:
				print pad
				print user_data
				gst.Pad.unlink(self.tee_video_pad_bin, self.queue_videobin_pad)
				self._logger.info("info: %s", str(info.id))
				self.tee_video_pad_bin.remove_probe(info.id)

				print self.streamProcessState
				if self.streamProcessState == 'TAKING_PHOTO':
					self._logger.info("ENTRA2")
					print self.queuebin.set_state(gst.State.PAUSED)
					print self.queuebin.set_state(gst.State.NULL)
	
					# print self.pipeline.set_state(gst.State.PAUSED)
					# print self.pipeline.set_state(gst.State.NULL)

					# self.pipeline.set_state(gst.State.NULL)
					# self.reset_pipeline_gstreamer_state()
					# self.streamProcessState = 'PAUSED'				
				self.waitForPhoto.set()
				return gst.PadProbeReturn.OK

			except Exception, error:
				self._logger.info("ERROR IN VIDEO_BIN_PAD_PROBE_CALLBACK: %s", error)

				if self.streamProcessState == 'TAKING_PHOTO':
					# self._logger.info("ENTRA'			
					print self.queuebin.set_state(gst.State.PAUSED)
					print self.queuebin.set_state(gst.State.NULL)

				self.waitForPhoto.set()
				self.fatalErrorManage(True, True)
				return gst.PadProbeReturn.DROP

		# self.sem.release()
		self.waitForPhoto.set()

		self._logger.info("VIDEO_BIN_PAD_PROBE_CALLBACK END")


		return gst.PadProbeReturn.OK

	def take_photo(self, textPhoto):
		self._logger.info("TAKE PHOTO")

		print textPhoto

		self.waitForPhoto = threading.Event()
		
		if self.streamProcessState == 'PREPARING_VIDEO' or self.streamProcessState == '':
			waitingState = self.waitForPhoto.wait(5)
			self.waitForPhoto.clear()
			
			# waitingState values:
			#  - True: exit before timeout. The device is able to take photo because video was stablished.
			#  - False: timeout given. The device is busy stablishing video. It is not able to take photo yet.

			if not waitingState:
				return None


		# threading.wait(5000)
		# self.sem = threading.Semaphore(0)

		# TAKES A PHOTO USING GSTREAMER
		self.take_photo_and_return(textPhoto)
		# THEN, WHEN PHOTO IS STORED, THIS IS REMOVED PHISICALLY
		# FROM HARD DISK FOR GETTING NEW PHOTOS AND FREEING SPACE
		photo = None
		try:
			waitingState = self.waitForPhoto.wait(10)
			# waitingState values:
			#  - True: exit before timeout
			#  - False: timeout given

			self._logger.info("WEAK UP WaitForPhoto")
			

			if self.streamProcessState == 'TAKING_PHOTO':

				self._logger.info("PIPE TO PAUSED")

				print self.pipeline.set_state(gst.State.PAUSED)

				self._logger.info("PIPE TO NULL")

				print self.pipeline.set_state(gst.State.NULL)

				self.reset_pipeline_gstreamer_state()

			# self.sem.acquire()
			# while photo is None:
			# 	time.sleep(1)
			# 	self._logger.info("ESPERANDO....'
			
			if waitingState:

				self._logger.info("OPENING FILE")

				with open('/tmp/gstCapture.jpg', 'r') as fin:
					photo = fin.read()
				self._logger.info("ANTES")
				os.unlink('/tmp/gstCapture.jpg')
				self._logger.info("DESPUES")
			
			else:
				return None

			self.waitForPhoto.clear()
		except Exception, error:

			if self.streamProcessState == 'TAKING_PHOTO':

				self._logger.info("PIPE TO PAUSED")

				print self.pipeline.set_state(gst.State.PAUSED)

				self._logger.info("PIPE TO NULL")

				print self.pipeline.set_state(gst.State.NULL)

				self.reset_pipeline_gstreamer_state()


			"""if self.photoMode == 'NOT_TEXT':

				print self.queuebinNotText.set_state(gst.State.PAUSED)
				print self.queuebinNotText.set_state(gst.State.NULL)
			else:
				print self.queuebin.set_state(gst.State.PAUSED)
				print self.queuebin.set_state(gst.State.NULL)
			"""
			self._logger.error("take_photo except:  %s" % str(error))
			self.waitForPhoto.clear()
			return None

		return photo

	def take_photo_and_return(self, textPhoto):
		self._logger.info("TAKE PHOTO AND RETURN")
		# TAKES A PHOTO USING GSTREAMER
		try:	
			print self.streamProcessState
			try:
				if self.streamProcessState == 'PAUSED':
	
					# SETTING THE TEXT INFORMATION ABOUT THE PRINTING STATE IN PHOTO
					if textPhoto is None:
						# CONFIGURATION FOR TAKING SOME FILES (PHOTO) FOR GETTING
						# A GOOD IMAGE FROM CAMERA
						self.multifilesinkphotoNotText = gst.ElementFactory.make('multifilesink', 'multifilesikNotText')
						self.multifilesinkphotoNotText.set_property('location', self.tempImage)
						self.multifilesinkphotoNotText.set_property('max-files', 1)
						self.multifilesinkphotoNotText.set_property('post-messages', True)				


						# QUEUE FOR TAKING PHOTOS    
						self.queuebinNotText = gst.ElementFactory.make('queue', 'queuebinNotText')
						# ##

						# ADDING PHOTO QUEUE TO PIPELINE
						self.pipeline.add(self.queuebinNotText)
						self.pipeline.add(self.jpeg_capsNotText)
						self.pipeline.add(self.jpegencNotText)
						# #
				
						# LINKING PHOTO ELEMENTS (WITHOUT TEXT ON PHOTO)
						self.queuebinNotText.link(self.jpeg_capsNotText)
						self.jpeg_capsNotText.link(self.jpegencNotText)
						##########
					
						self.pipeline.add(self.multifilesinkphotoNotText)
						# self.jpegenc.link(self.multifilesinkphoto)	
					
					else:


						print textPhoto

						# CONFIGURATION FOR TAKING SOME FILES (PHOTO) FOR GETTING
						# A GOOD IMAGE FROM CAMERA
						self.multifilesinkphoto = gst.ElementFactory.make('multifilesink', 'multifilesink')
						self.multifilesinkphoto.set_property('location', self.tempImage)
						self.multifilesinkphoto.set_property('max-files', 1)
						self.multifilesinkphoto.set_property('post-messages', True)				


						# QUEUE FOR TAKING PHOTOS    
						self.queuebin = gst.ElementFactory.make('queue', 'queuebin')
						# ##

						# ADDING PHOTO QUEUE TO PIPELINE
						self.pipeline.add(self.queuebin)
						self.pipeline.add(self.jpeg_caps)
						self.pipeline.add(self.photo_logo)
						self.pipeline.add(self.photo_text)
						self.pipeline.add(self.jpegenc)
						# #
				
						# SETTING THE TEXT INFORMATION ABOUT THE PRINTING STATE IN PHOTO
						# text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>" + textPhoto + "</span>"
						# self.photo_text.set_property('text',text)
						# LINKING PHOTO ELEMENTS (INCLUDED TEXT)
						self.queuebin.link(self.jpeg_caps)
						self.jpeg_caps.link(self.photo_logo)
						self.photo_logo.link(self.photo_text)
						self.photo_text.link(self.jpegenc)
		
						self.pipeline.add(self.multifilesinkphoto)
						# self.jpegenc.link(self.multifilesinkphoto)	

					print self.streamProcessState
			
					self.streamProcessState = 'TAKING_PHOTO'
				
					self.pipeline.set_state(gst.State.PLAYING)

			except Exception, error:
				self._logger.info("ERROR IN TAKE PHOTO AND RETURN WITH VIDEO PAUSED: %s" % str(error))

				self._logger.error("Error taking photo with GStreamer: %s" % str(error))
				self.pipeline.set_state(gst.State.PAUSED)
				self.pipeline.set_state(gst.State.NULL)
				self.reset_pipeline_gstreamer_state()

				return None				


			###############

			if textPhoto is None:
				try:
					self.photoMode = 'NOT_TEXT'

					self._logger.info("PREPARING WITHOUT TEXT")
					# self.pipeline.add(self.multifilesinkphoto)
					self.jpegencNotText.link(self.multifilesinkphotoNotText)


					self.tee_video_pad_binNotText = self.tee.get_request_pad("src_%u")
					self.queue_videobin_padNotText = self.queuebinNotText.get_static_pad("sink")	

					print gst.Pad.link(self.tee_video_pad_binNotText, self.queue_videobin_padNotText)

					print self.queuebinNotText.set_state(gst.State.PLAYING)

				except Exception, error:
					self._logger.error("ERROR IN TAKING PHOTO AND RETURN WITH TEXTPHOTO: %s" % str(error))
					self._logger.error("Error taking photo with GStreamer: %s" % str(error))
	                                self.pipeline.set_state(gst.State.PAUSED)
        	                        self.pipeline.set_state(gst.State.NULL)
                	                self.reset_pipeline_gstreamer_state()
				
			else:

				try:

					# SETTING THE TEXT INFORMATION ABOUT THE PRINTING STATE IN PHOTO
					text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>" + textPhoto + "</span>"
					self.photo_text.set_property('text', text)

					self.photoMode = 'TEXT'

					self._logger.info("PREPARING WITH TEXT")
				
					# self.pipeline.add(self.multifilesinkphoto)
					self.jpegenc.link(self.multifilesinkphoto)	


					self.tee_video_pad_bin = self.tee.get_request_pad("src_%u")
					self.queue_videobin_pad = self.queuebin.get_static_pad("sink")	
	
					print gst.Pad.link(self.tee_video_pad_bin, self.queue_videobin_pad)

					print self.queuebin.set_state(gst.State.PLAYING)

				except Exception, error:
					self._logger.info("ERROR IN TAKING PHOTO AND RETURN WITHOUT TEXTPHOTO: %s" % str(error))
					self._logger.error("Error taking photo with GStreamer: %s" % str(error))
	                                self.pipeline.set_state(gst.State.PAUSED)
        	                        self.pipeline.set_state(gst.State.NULL)
                	                self.reset_pipeline_gstreamer_state()


			#########
			# time.sleep(1)

			return None

		except Exception, error:
			
			self._logger.error("Error taking photo with GStreamer: %s" % str(error))
			self.pipeline.set_state(gst.State.PAUSED)
			self.pipeline.set_state(gst.State.NULL)
			self.reset_pipeline_gstreamer_state()
			
			return None

		
	def getStreamProcessState(self):
		# RETURNS THE CURRENT STREAM STATE
		return self.streamProcessState

	def fatalErrorManage(self, NULLToQueuebinNotText=True, NULLToQueuebin=True):
		
		if NULLToQueuebinNotText and self.queuebinNotText:
				self.queuebinNotText.set_state(gst.State.PAUSED)
				self.queuebinNotText.set_state(gst.State.NULL)
		
		if NULLToQueuebin and self.queuebin:
			self.queuebin.set_state(gst.State.PAUSED)
			self.queuebin.set_state(gst.State.NULL)
		
		self.pipeline.set_state(gst.State.PAUSED)
		self.pipeline.set_state(gst.State.NULL)
		self.reset_pipeline_gstreamer_state()

		self._logger.info('sending manage_fatal_error signal')

		ready = signal('manage_fatal_error')
		ready.send(self)

