import gi
import time
import logging

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
            
            self.videotype = videotype
            self.size = size.split('x')
            self.framerate = framerate
            
            self.video_source = gst.ElementFactory.make('v4l2src', 'video_source')
            self.video_source.set_property("device", "/dev/video0")
    
            self.video_logo = gst.ElementFactory.make('gdkpixbufoverlay','logo_overlay')
            self.video_logo.set_property('location','/AstroBox/src/astroprint/static/img/astroprint_logo.png')
            self.video_logo.set_property('offset-x',480)
            self.video_logo.set_property('offset-y',450)
            self.video_logo.set_property('overlay-width',150)
            self.video_logo.set_property('overlay-height',29)
    
            camera1caps = gst.Caps.from_string('video/x-raw, width=' + size[0] + ',height=' + size[1] + ',framerate=' + framerate + '\'')
            self.src_caps = gst.ElementFactory.make("capsfilter", "filter1")
            self.src_caps.set_property("caps", camera1caps)
            
            #####################
            
            self.photo_logo = gst.ElementFactory.make('gdkpixbufoverlay')
            self.photo_logo.set_property('location','/AstroBox/src/astroprint/static/img/camera-info-overlay.jpg')
            self.photo_logo.set_property('offset-x',0)
            self.photo_logo.set_property('offset-y',0)
            
            self.photo_text = gst.ElementFactory.make('textoverlay')
            text = "<span foreground='#eb1716' background='white' font='nexa_boldregular' size='large'>0% - Layer - 1 / 114 </span>"
            self.photo_text.set_property('text',text)
            self.photo_text.set_property('valignment','top')
            self.photo_text.set_property('ypad',0)
            self.photo_text.set_property('halignment','left')
            self.photo_text.set_property('xpad',35)
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
            self.reset_pipeline_gstreamer_state()
            
            return False
        
    def play_video(self):
        
        try:
            
            print 'PLAY_VIDEO'
            
            queueraw = gst.ElementFactory.make('queue','queueraw')
            
            udpsinkout = gst.ElementFactory.make('udpsink','udpsink')
            udpsinkout.set_property('host','127.0.0.1')
    
            if self.videotype == 'h264':
    
                encode = gst.ElementFactory.make('omxh264enc',None)
    
                camera1capsout = gst.Caps.from_string('video/x-h264,profile=high')
                enc_caps = gst.ElementFactory.make("capsfilter", "filter2")
                enc_caps.set_property("caps", camera1capsout)
                
                videortppay = gst.ElementFactory.make('rtph264pay','rtph264pay')
                videortppay.set_property('pt',96)
    
                udpsinkout.set_property('port',8004)
                
            elif self.videotype == 'vp8':
                
                encode = gst.ElementFactory.make('vp8enc',None)
                encode.set_property('target-bitrate',500000)
                encode.set_property('keyframe-max-dist',500)
                encode.set_property('deadline',1)
                
                
                videortppay = gst.ElementFactory.make('rtpvp8pay','rtpvp8pay')
                videortppay.set_property('pt',96)
                
                udpsinkout.set_property('port',8005)
                
            self.queuebin = gst.ElementFactory.make('queue','queuebin')
    
            filesinkbin= gst.ElementFactory.make('filesink','filesink')
            filesinkbin.set_property('location','/dev/null')
            
            jpegenc = gst.ElementFactory.make('jpegenc','jpegenc')
            
            multifilesinkphoto = gst.ElementFactory.make('multifilesink','appsink')
            multifilesinkphoto.set_property('location','/tmp/gstCapture.jpg')
            multifilesinkphoto.set_property('max-files',1)
            
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
            self.pipeline.add(jpegenc)
            self.pipeline.add(multifilesinkphoto)
            
            
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
            self.photo_text.link(jpegenc)
            jpegenc.link(multifilesinkphoto)
            
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
    
            # Wait until error or EOS
            bus = self.pipeline.get_bus()
            bus.timed_pop_filtered(gst.CLOCK_TIME_NONE, gst.MessageType.ERROR | gst.MessageType.EOS)
            
            bus.add_signal_watch()
            #bus.connect('message::eos', self.on_eos)
            #bus.connect('message::error', self.on_error)
            
            # This is needed to make the video output in our DrawingArea:
            #bus.enable_sync_message_emission()
            #bus.connect('sync-message::element', self.on_sync_message)
            
            # Free resources
            #self.pipeline.set_state(gst.State.NULL)
            
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

    def take_photo(self):
        
        try:
        
            if self.streamProcessState == 'PLAYING':
                
                gst.Pad.link(self.tee_video_pad_bin,self.queue_videobin_pad)
            
                time.sleep(1)
            
                self.queuebin.unlink(self.photo_logo)
                gst.Pad.unlink(self.tee_video_pad_bin,self.queue_videobin_pad)
                
            elif self.streamProcessState == 'PAUSED':
                
                self.queuebin = gst.ElementFactory.make('queue','queuebin')
    
                jpegenc = gst.ElementFactory.make('jpegenc','jpegenc')
                
                multifilesinkphoto = gst.ElementFactory.make('multifilesink','appsink')
                multifilesinkphoto.set_property('location','/tmp/gstCapture.jpg')
                multifilesinkphoto.set_property('max-files',1)
                
                # Create the empty pipeline
                self.pipeline = gst.Pipeline()
                self.pipeline.set_property('name','tee-pipeline')
                
                ##
                self.pipeline.add(self.queuebin)
                self.pipeline.add(self.photo_logo)
                self.pipeline.add(self.photo_text)
                self.pipeline.add(jpegenc)
                self.pipeline.add(multifilesinkphoto)
                
                #LINKS
                self.queuebin.link(self.photo_logo)
                self.photo_logo.link(self.photo_text)
                self.photo_text.link(jpegenc)
                ###
                jpegenc.link(multifilesinkphoto)
                
                self.tee_video_pad_bin = self.tee.get_request_pad("src_%u")
                
                self.queue_videobin_pad = self.queuebin.get_static_pad("sink")
                
                gst.Pad.link(self.tee_video_pad_bin,self.queue_videobin_pad)
                
                self.pipeline.set_state(gst.State.PLAYING)
                self.streamProcessState = 'TAKING PHOTO'
                
                time.sleep(1)
                
                self.pipeline.set_state(gst.State.PAUSED)
                self.pipeline.set_state(gst.State.NULL)
                
                
                file_source = gst.ElementFactory.make('filesrc','filesrc')
                file_source.set_property('location','/tmp/gstCapture.jpg')
                
                jpeg_dec = gst.ElementFactory.make('jpegdec','jpegdec')
                
                file_sinkout = gst.ElementFactory.make('filesink','filesink')
                file_sinkout.set_property('location','/dev/stdout')
                
                self.pipeline = gst.Pipeline()
                self.pipeline.set_property('name','jpeg-out-pipeline')
                
                self.pipeline.add(file_source)
                self.pipeline.add(jpeg_dec)
                self.pipeline.add(file_sinkout)
                
                file_source.link(jpeg_dec)
                jpeg_dec.link(file_sinkout)
                
                self.pipeline.set_state(gst.State.PLAYING)
                
                # Wait until error or EOS
                bus = self.pipeline.get_bus()
                bus.timed_pop_filtered(gst.CLOCK_TIME_NONE, gst.MessageType.ERROR | gst.MessageType.EOS)
                
                bus.add_signal_watch()
                #bus.connect('message::eos', self.on_eos)
                #bus.connect('message::error', self.on_error)
                
                # This is needed to make the video output in our DrawingArea:
                bus.enable_sync_message_emission()
                #bus.connect('sync-message::element', self.on_sync_message)
                
                # Free resources
                self.pipeline.set_state(gst.State.NULL)
                
                self.reset_pipeline_gstreamer_state()
        
            return True
        
        except Exception, error:
            
            self._logger.error("Error taking photo with GStreamer: %s" % str(error))
            self.pipeline.set_state(gst.State.PAUSED)
            self.pipeline.set_state(gst.State.NULL)
            self.reset_pipeline_gstreamer_state()
            
            return False
        
    def getStreamProcessState(self):
        
        return self.streamProcessState 
###