import gi
import time
import logging
import os
from octoprint.settings import settings

gi.require_version('Gst','1.0')
from gi.repository import GObject as gobject
from gi.repository import Gst as gst

gobject.threads_init()
gst.init(None)

class GstreamerVideo(object):
    
    def __init__(self,videotype,size,framerate):
        
        self._logger = logging.getLogger(__name__)
        
        try:

            print 'TRY GSTREAMERVIDEO.INIT'
            
            self.video_source = gst.ElementFactory.make('v4l2src', 'video_source')
            self.video_source.set_property("device", "/dev/video0")


            self.video_logo = gst.ElementFactory.make('gdkpixbufoverlay','logo_overlay')
            self.video_logo.set_property('location','/AstroBox/src/astroprint/static/img/astroprint_logo.png')
            self.video_logo.set_property('overlay-width',150)
            self.video_logo.set_property('overlay-height',29)
    
            #####################
            
            self.photo_logo = gst.ElementFactory.make('gdkpixbufoverlay')
            self.photo_logo.set_property('location','/AstroBox/src/astroprint/static/img/camera-info-overlay.jpg')
            self.photo_logo.set_property('offset-x',0)
            self.photo_logo.set_property('offset-y',0)
            
            self.photo_text = gst.ElementFactory.make('textoverlay')
            text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>0% - Layer - X / X </span>"
            self.photo_text.set_property('text',text)
            self.photo_text.set_property('valignment','top')
            self.photo_text.set_property('ypad',0)
            self.photo_text.set_property('halignment','left')
            self.photo_text.set_property('xpad',35)


	    self.videoscalejpeg = gst.ElementFactory.make('videoscale','videoscale')
	    camerajpegcaps = gst.Caps.from_string('video/x-raw,width=640,height=480,framerate=15/1')
            self.jpeg_caps = gst.ElementFactory.make("capsfilter", "filterjpeg")
            self.jpeg_caps.set_property("caps", camerajpegcaps)

            self.jpegenc = gst.ElementFactory.make('jpegenc','jpegenc')
            #####################
            
            self.reset_pipeline_gstreamer_state()
            
        except Exception, error:
            
            print 'EXCEPTION GSTREAMERVIDEO.INIT'
            
            self._logger.error("Error initializing GStreamer's video pipeline: %s" % str(error))
            self.pipeline.set_state(gst.State.PAUSED)
            self.pipeline.set_state(gst.State.NULL)
            self.reset_pipeline_gstreamer_state()
        
        
    def reset_pipeline_gstreamer_state(self):
        
        try:

	    self.videotype = settings().get(["camera", "encoding"])
	    self.size = settings().get(["camera", "size"]).split('x')
	    self.framerate = settings().get(["camera", "framerate"])


            self.video_logo.set_property('offset-x',int(self.size[0])-160)
            self.video_logo.set_property('offset-y',int(self.size[1])-30)
            print 'video/x-raw, width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate + '/1'
            camera1caps = gst.Caps.from_string('video/x-raw,width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate + '/1')

            self.src_caps = gst.ElementFactory.make("capsfilter", "filter1")
            self.src_caps.set_property("caps", camera1caps)


            self.tee = gst.ElementFactory.make('tee','tee')
            
            self.pipeline = gst.Pipeline()
            self.pipeline.set_property('name','tee-pipeline')
            
            self.pipeline.add(self.video_source)
            self.pipeline.add(self.video_logo)
            self.pipeline.add(self.src_caps)
            self.pipeline.add(self.tee)
           
            #LINKS
            self.video_source.link(self.video_logo)
            self.video_logo.link(self.src_caps)
            self.src_caps.link(self.tee)
            
            self.queuebin = None
            self.tee_video_pad_bin = None        
            self.queue_videobin_pad = None
            
            self.streamProcessState = 'PAUSED'
            
            return True
        
        except Exception, error:
            
            self._logger.error("Error resetting GStreamer's video pipeline: %s" % str(error))
            self.pipeline.set_state(gst.State.PAUSED)
            self.pipeline.set_state(gst.State.NULL)
            
            return False
        
    def play_video(self):
        
        try:
            
            print 'PLAY_VIDEO'

	    self.videotype = settings().get(["camera", "encoding"])
	    self.size = settings().get(["camera", "size"]).split('x')
	    self.frameratee = settings().get(["camera", "framerate"])


            self.video_logo.set_property('offset-x',int(self.size[0])-160)
            self.video_logo.set_property('offset-y',int(self.size[1])-30)
            print 'video/x-raw, width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate + '/1'
            camera1caps = gst.Caps.from_string('video/x-raw,width=' + self.size[0] + ',height=' + self.size[1] + ',framerate=' + self.framerate + '/1')
            self.src_caps = gst.ElementFactory.make("capsfilter", "filter1")
            self.src_caps.set_property("caps", camera1caps)
                    
            queueraw = gst.ElementFactory.make('queue','queueraw')
            
            udpsinkout = gst.ElementFactory.make('udpsink','appsink')
            udpsinkout.set_property('host','127.0.0.1')
    
            if self.videotype == 'h264':

		print 'H264'

                encode = gst.ElementFactory.make('omxh264enc',None)
    
                camera1capsout = gst.Caps.from_string('video/x-h264,profile=high')
                enc_caps = gst.ElementFactory.make("capsfilter", "filter2")
                enc_caps.set_property("caps", camera1capsout)
                
                videortppay = gst.ElementFactory.make('rtph264pay','rtph264pay')
                videortppay.set_property('pt',96)
    
                udpsinkout.set_property('port',8004)
                
            elif self.videotype == 'vp8':

		print 'VP8'

                encode = gst.ElementFactory.make('vp8enc',None)
                encode.set_property('target-bitrate',500000)
                encode.set_property('keyframe-max-dist',500)
                encode.set_property('deadline',1)
                
                
                videortppay = gst.ElementFactory.make('rtpvp8pay','rtpvp8pay')
                videortppay.set_property('pt',96)
                
                udpsinkout.set_property('port',8005)
                
            self.queuebin = gst.ElementFactory.make('queue','queuebin')
            
            ##VIDEO
            self.pipeline.add(queueraw)
            self.pipeline.add(encode)
            
            if self.videotype == 'h264':
                self.pipeline.add(enc_caps)
                
            self.pipeline.add(videortppay)
            self.pipeline.add(udpsinkout)
            ##PHOTO
            self.pipeline.add(self.queuebin)
            self.pipeline.add(self.photo_logo)
            self.pipeline.add(self.photo_text)
	    self.pipeline.add(self.videoscalejpeg)
	    self.pipeline.add(self.jpeg_caps)
            self.pipeline.add(self.jpegenc)
           
            
            #LINKS
            ##VIDEO
            queueraw.link(encode)
            
            if self.videotype == 'h264':
                encode.link(enc_caps)
                enc_caps.link(videortppay)
            else:
                encode.link(videortppay)
                
            videortppay.link(udpsinkout)
            ##PHOTO
            self.queuebin.link(self.photo_logo)
            self.photo_logo.link(self.photo_text)
            self.photo_text.link(self.jpegenc)
            #TEE PADDING MANAGING
            ##TEE SOURCE H264
            tee_video_pad_video = self.tee.get_request_pad("src_%u")
            ##TEE SOURCE PHOTO
            self.tee_video_pad_bin = self.tee.get_request_pad("src_%u")
            
            #TEE SINKING MANAGING
            ##VIDEO SINK QUEUE
            queue_video_pad = queueraw.get_static_pad("sink")
            ##PHOTO SINK QUEUE
            self.queue_videobin_pad = self.queuebin.get_static_pad("sink")
    
            #TEE PAD LINK
            ##VIDEO PADDING        
            gst.Pad.link(tee_video_pad_video,queue_video_pad)
              
            # Start playing the pipeline
            print self.pipeline.set_state(gst.State.PLAYING)
            self.streamProcessState = 'PLAYING'
    
            print 'BEFORE RET'
            return True
            
        except Exception, error:
            
            self._logger.error("Error playing video with GStreamer: %s" % str(error))
            self.pipeline.set_state(gst.State.PAUSED)
            self.pipeline.set_state(gst.State.NULL)
            self.reset_pipeline_gstreamer_state()
            
            return False
        
    def stop_video(self):
        
        try:
        
            if self.streamProcessState == 'PLAYING': 
                self.queuebin = None
                self.pipeline.set_state(gst.State.PAUSED)
                self.pipeline.set_state(gst.State.NULL)
                self.reset_pipeline_gstreamer_state()
            
            return True
                
        except Exception, error:
            
            self._logger.error("Error stopping video with GStreamer: %s" % str(error))
            self.pipeline.set_state(gst.State.PAUSED)
            self.pipeline.set_state(gst.State.NULL)
            self.reset_pipeline_gstreamer_state()
            
            return False

    def take_photo(self,textPhoto):

	photo = self.take_photo_and_return(textPhoto)

	try:
		os.unlink('/tmp/gstCapture.jpg')

	except:
		pass

	return photo

		

    def take_photo_and_return(self,textPhoto):
        
	try:
        
	    tempImage = '/tmp/gstCapture.jpg'
	
            #text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>0% - Layer - X / X </span>"

	    if textPhoto is not None:
                text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>" + textPhoto + "</span>"
                photo_text.set_property('text',text)

            multifilesinkphoto = gst.ElementFactory.make('filesink','appsink')
            multifilesinkphoto.set_property('location','/dev/stdout')
            #multifilesinkphoto.set_property('max-files',1)

	    if self.streamProcessState == 'PLAYING':

		print 'VIDEO IS PLAYING'

		##PREPARING PHOTO

		if textPhoto is not None:
	               	text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>" + textPhoto + "</span>"
	                self.photo_text.set_property('text',text)

			self.queuebin.link(self.photo_logo)
			self.photo_logo.link(self.videoscalejpeg)
			self.videoscalejpeg.link(self.jpeg_caps)
			self.jpeg_caps.link(self.photo_text)
			self.photo_text.link(self.jpgegenc)
		else:
			self.queuebin.link(self.videoscalejpeg)
		        self.videoscalejpeg.link(self.jpeg_caps)
			self.jpeg_caps.link(self.jpegenc)

		self.pipeline.add(multifilesinkphoto)
            	self.jpegenc.link(multifilesinkphoto)


                gst.Pad.link(self.tee_video_pad_bin,self.queue_videobin_pad)
            
		#############
		##TAKING PHOTO
		import time
		
		while not os.path.isfile('/tmp/gstCapture.jpg'):
			time.sleep(0.1)
		time.sleep(1)

		##############
		##DISCONNECTING PHOTO PIPE

		self.jpegenc.unlink(multifilesinkphoto)

                gst.Pad.unlink(self.tee_video_pad_bin,self.queue_videobin_pad)

		self.pipeline.remove(multifilesinkphoto)

            elif self.streamProcessState == 'PAUSED':

		print 'VIDEO IS PAUSED'

		video_source = gst.ElementFactory.make('v4l2src', 'video_source')
		video_source.set_property("device", "/dev/video0")

		video_logo = gst.ElementFactory.make('gdkpixbufoverlay','logo_overlay')
		video_logo.set_property('location','/AstroBox/src/astroprint/static/img/astroprint_logo.png')

                video_logo.set_property('offset-x',int(self.size[0])-160)
                video_logo.set_property('offset-y',int(self.size[1])-30)

		video_logo.set_property('overlay-width',150)
		video_logo.set_property('overlay-height',29)

		camera1caps = gst.Caps.from_string('video/x-raw,width=640,height=480,framerate=5/1')
		src_caps = gst.ElementFactory.make("capsfilter", "filter1")
		src_caps.set_property("caps", camera1caps)

		tee = gst.ElementFactory.make('tee','tee')

		queuebin = gst.ElementFactory.make('queue','queuebin')

		videoconvert = gst.ElementFactory.make('videoconvert','videoconvertbin')
		rtpvrawpay = gst.ElementFactory.make('rtpvrawpay','rtpvrawpay')

		filesinkbin= gst.ElementFactory.make('filesink','filesink')
		filesinkbin.set_property('location','/dev/null')


		if textPhoto is not None:
			photo_logo = gst.ElementFactory.make('gdkpixbufoverlay')
			photo_logo.set_property('location','/AstroBox/src/astroprint/static/img/camera-info-overlay.jpg')
			photo_logo.set_property('offset-x',0)
			photo_logo.set_property('offset-y',0)

			photo_text = gst.ElementFactory.make('textoverlay')
	               	text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>" + textPhoto + "</span>"
	                photo_text.set_property('text',text)
			photo_text.set_property('text',text)
			photo_text.set_property('valignment','top')
			photo_text.set_property('ypad',0)
			photo_text.set_property('halignment','left')
			photo_text.set_property('xpad',35)

		pngenc = gst.ElementFactory.make('pngenc','pngenc')

		multifilesinkphoto = gst.ElementFactory.make('multifilesink','appsink')
		multifilesinkphoto.set_property('location','/tmp/gstCapture.jpg')

		multifilesinkphoto.set_property('max-files',1)

		# Create the empty pipeline
		pipeline = gst.Pipeline()
		pipeline.set_property('name','tee-pipeline')

		pipeline.add(video_source)
		pipeline.add(video_logo)
		pipeline.add(src_caps)
		pipeline.add(tee)
		##
		pipeline.add(queuebin)
		if textPhoto is not None:
			pipeline.add(photo_logo)
			pipeline.add(photo_text)
		pipeline.add(pngenc)
		pipeline.add(multifilesinkphoto)

		#LINKS
		video_source.link(video_logo)
		video_logo.link(src_caps)
		src_caps.link(tee)
		
		if textPhoto is not None:
			queuebin.link(photo_logo)
			photo_logo.link(photo_text)
			photo_text.link(pngenc)
		else:
			
			queuebin.link(pngenc)
		###
		pngenc.link(multifilesinkphoto)

		tee_video_pad_bin = tee.get_request_pad("src_%u")


		queue_videobin_pad = queuebin.get_static_pad("sink")

		print gst.Pad.link(tee_video_pad_bin,queue_videobin_pad)
	
		ret = pipeline.set_state(gst.State.PLAYING)


		###
		import time
		
		while not os.path.isfile('/tmp/gstCapture.jpg'):
			time.sleep(0.1)
		time.sleep(1)
		###

		print 'outing'

		pipeline.set_state(gst.State.PAUSED)
		pipeline.set_state(gst.State.NULL)
		
                
	    with open('/tmp/gstCapture.jpg','r') as fin:
		    return fin.read()        

        except Exception, error:
            
            self._logger.error("Error taking photo with GStreamer: %s" % str(error))
            self.pipeline.set_state(gst.State.PAUSED)
            self.pipeline.set_state(gst.State.NULL)
            self.reset_pipeline_gstreamer_state()
            
            return None
        
    def getStreamProcessState(self):
        
        return self.streamProcessState 
###
