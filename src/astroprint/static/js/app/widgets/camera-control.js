var CameraControlView = Backbone.View.extend({
  cameraMode: 'video',//['video','photo']
  state: null,
  canStream: false,
  cameraAvailable: false,
  cameraNotSupported: false,
  browserNotVisibleManager: null,
  browserVisibilityState: null,
  initCamera: function(settings)
  {
    this.videoStreamingError = null;

    $.getJSON(API_BASEURL + 'camera/connected')
    .done(_.bind(function(response){

      if(response.isCameraConnected){

        $.getJSON(API_BASEURL + 'camera/is-camera-supported')
        .done(_.bind(function(response){

          if(response.isCameraSupported){

            this.cameraNotSupported = false;

            $.getJSON(API_BASEURL + 'camera/has-properties')
            .done(_.bind(function(response){
                if(response.hasCameraProperties){
                  this.cameraAvailable = true;
                  //video settings
                  if( settings ){
                    this.settings = settings;
                    this.cameraInitialized();

                  } else {
                    $.getJSON(API_BASEURL + 'settings/camera')
                    .done(_.bind(function(settings){

                      this.settings = settings;
                      this.cameraInitialized();

                    },this));
                  }

                  this.render();
                } else {
                  this.cameraAvailable = false;
                  this.videoStreamingError = 'Camera error: Unable to read the camera capabilities. Reconnect the camera and try again...';
                  this.render();
                }
            },this))
            .fail(_.bind(function(response){
              this.cameraAvailable = false;
              noty({text: "Unable to communicate with the camera.", timeout: 3000});
              this.stopStreaming();
              this.setState('error');
            },this));
          } else {
            this.cameraAvailable = true;
            this.cameraNotSupported = true;
            this.render();
          }
        },this))
        .fail(_.bind(function(response){
          this.cameraAvailable = false;
          noty({text: "Unable to communicate with the camera.", timeout: 3000});
          this.stopStreaming();
          this.setState('error');
        },this));
      } else {
        this.cameraAvailable = false;
        this.render();
      }
    },this))
  },
  buttonEvent: function()
  {
    if(this.cameraMode == 'video'){
      if(this.state == 'streaming'){
        this.deactivateWindowHideListener();
        return this.stopStreaming();
      } else {
        return this.startStreaming();
      }
    } else { //photo
      return this.takePhoto();
    }
  },
  render: function()
  {
    this.$el.html(this.template());
  },
  cameraModeChanged: function(e)
  {
    e.preventDefault();

    if(this.cameraMode == 'video'){
      this.stopStreaming();
      this.$el.removeClass('nowebrtc error');
    }
    this.cameraMode = this.cameraModeByValue($(e.currentTarget).is(':checked'));
    this.render();
  },
  cameraModeByValue: function(value)
  {
    /* Values matches by options:
    * - True: video mode
    * - False: photo mode
    */
    return value ? 'video' : 'photo';
  },
  onShow: function()
  {
    this.initCamera();
    this.$el.removeClass('nowebrtc error');
  },
  onHide: function()
  {
    if(this.cameraMode == 'video'){
      if(this.state == 'streaming'){
        this.stopStreaming();
      }
    } else {
      this.$('.camera-image').removeAttr('src');
    }
    this.setState('ready');
  },
  setState: function(state)
  {
    this.state = state;
    this.$el.removeClass('preparing error nowebrtc streaming ready').addClass(state)
  },
  takePhoto: function()
  {
    var promise = $.Deferred();

    photoCont = this.getPhotoContainer();

    photoCont.attr('src', '/camera/snapshot?apikey='+UI_API_KEY+'&timestamp=' + (Date.now() / 1000));

    photoCont.on('load',function() {
      photoCont.off('load');
      promise.resolve();
    });

    photoCont.on('error', function() {
      photoCont.removeAttr('src');
      photoCont.off('error');
      promise.reject();
    });

    return promise;
  },
  activateWindowHideListener: function()
  {
    var onVisibilityChange = _.bind(function() {
      if(document.hidden || document.visibilityState != 'visible'){
        setTimeout(_.bind(function(){
          if(document.hidden || document.visibilityState != 'visible'){
            this.stopStreaming();
            this.browserNotVisibleManager = 'waiting';
          }
        },this), 15000);
      } else {
        if(this.browserNotVisibleManager == 'waiting'){
          this.browserNotVisibleManager = null;
          this.startStreaming();
        }
      }
    },this);

    $(document).on("visibilitychange", onVisibilityChange);
  },
  deactivateWindowHideListener: function(){
    $(document).off("visibilitychange");
  },

  //Implement these
  cameraInitialized: function(){},
  startStreaming: function(){}, // return a promise
  stopStreaming: function(){}, // return a promise

  getPhotoContainer: function(){},
  getVideoContainer: function(){}
});

var CameraControlViewMJPEG = CameraControlView.extend({
  managerName: 'mjpeg',
  canStream: true,
  startStreaming: function()
  {
    var promise = $.Deferred();

    this.setState('preparing');

    $.ajax({
      url: API_BASEURL + 'camera/peer-session',
      method: 'POST',
      data: JSON.stringify({
        sessionId: AP_SESSION_ID
      }),
      contentType: 'application/json',
      type: 'json'
    })
      .done(_.bind(function(r){
        this.streaming = true;
        var videoCont = this.getVideoContainer();
        videoCont.attr('src', '/webcam/?action=stream&time='+new Date().getTime());

        videoCont.on('load', _.bind(function() {
          this.setState('streaming');
          this.activateWindowHideListener();
          videoCont.off('load');
          promise.resolve();
        },this));

        videoCont.on('error', _.bind(function(e) {
          videoCont.off('error');
          this.videoStreamingError = 'Error while playing video';
          this.render();
          promise.reject()
        },this));
      }, this))
      .fail(_.bind(function(xhr){
        this.videoStreamingError = 'Unable to start video session. (' + xhr.status + ')';
        this.render();
        promise.reject()
      }, this))

    return promise;
  },
  stopStreaming: function()
  {
    var promise = $.Deferred();

    $.ajax({
      url: API_BASEURL + 'camera/peer-session',
      method: 'DELETE',
      type: 'json',
      contentType: 'application/json',
      data: JSON.stringify({
        sessionId: AP_SESSION_ID
      })
    })
      .done(_.bind(function(){
        this.setState('ready');
        promise.resolve();
      }, this))
      .fail(function(){
        promise.reject();
      });

    return promise;
  }
});

var CameraControlViewWebRTC = CameraControlView.extend({
  el: null,
  serverUrl: null,
  streamingPlugIn: null,
  streaming: false,
  managerName: 'webrtc',
  stoppingPromise: null,
  events: {
  'hide':'onHide'
  },
  settings: null,
  print_capture: null,
  photoSeq: 0,
  _socket: null,
  videoStreamingEvent: null,
  videoStreamingError: null,
  videoStreamingErrorTitle: null,
  originalFunctions: null,//this could be contained the original functions
  //startStreaming, stopStreaming, and onHide for being putted back after changing
  //settings if new settings ables to get video instead of old settings
  timeoutPlayingManager: null,
  manageVideoStreamingEvent: function(value)
  {//override this for managing this error
    this.videoStreamingError = value.message;
    if('camera settings have been changed'.indexOf(value.message) >-1){
      this.videoStreamingErrorTitle = 'Camera settings changed'
    } else {
      this.videoStreamingErrorTitle = null;
    }

    console.error(value.message);
    },
    _onVideoStreamingError: function(e)
    {
    if (e.data && e.data['event']) {
      var data = e.data['event'];
      var type = data["type"];

      if (type == 'GstreamerFatalErrorManage') {
        this.manageVideoStreaming(data["message"]);
      }
    }
  },
  cameraInitialized: function()
  {
    //Evaluate if we are able to do WebRTC

    if(Janus.isWebrtcSupported()) {
      this.setState('ready');
      this.canStream = true;
    } else {
      this.setState('nowebrtc');
      this.canStream = false;
    }

    this.canStream = true;

    if( !this.canStream){

      if( !this.originalFunctions) {
        this.originalFunctions = new Object();
        this.originalFunctions.startStreaming = this.startStreaming;
        this.originalFunctions.stopStreaming = this.stopStreaming;
        this.originalFunctions.onHide = this.onHide;
        this.originalFunctions.initJanus = this.initJanus;
      }

      this.initJanus = null;

      this.startStreaming = function(){ this.setState('nowebrtc'); return $.Deferred().resolve(); };
      this.stopStreaming = function(){ return $.Deferred().resolve(); };
      this.onHide = function(){ return true; };
      //this.setState('nowebrtc');
      this.cameraMode = 'photo';
    } else {

      if( this.originalFunctions) {
        this.startStreaming = this.originalFunctions.startStreaming;
        this.stopStreaming = this.originalFunctions.stopStreaming;
        this.onHide = this.originalFunctions.onHide;
        this.initJanus = this.originalFunctions.initJanus;
      }

      this.serverUrl = "http://" + window.location.hostname + ":8088/janus";

      this.initJanus();

      // Initialize the library (all console debuggers enabled)
      Janus.init({debug: false, callback: function() {
        console.log('Janus Initialized')
      }});
    }
    this.render();
  },
  initJanus: function()
  {
    this.streaming = false;
    this.streamingPlugIn = null;
  },
  startStreaming: function()
  {
    var promise = $.Deferred();

    var videoCont = this.getVideoContainer();

    this.setState('preparing');
    $.ajax({
      url: API_BASEURL + "camera/init-janus",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: ''
    })
    .done(_.bind(function(isJanusRunning){
      if(!videoCont.is(':visible')) {
        // Create session
        var janus = new Janus({
          server: this.serverUrl,
          apisecret: 'd5faa25fe8e3438d826efb1cd3369a50',
          iceServers: [{
            "urls": ["stun:turn.astroprint.com:80"]
          }],
          success: _.bind(function() {
            $.ajax({
              url: API_BASEURL + "camera/peer-session",
              type: "POST",
              data: JSON.stringify({
                sessionId: AP_SESSION_ID
              }),
              dataType: "json",
              contentType: "application/json; charset=UTF-8",
            })
            .fail(_.bind(function(){
              noty({text: "Unable to start WebRTC session.", timeout: 3000});
              this.setState('error');
            }, this))
            .done(_.bind(function(response) {
              this.streaming = true;

              var streamingPlugIn = null;
              var selectedStream = this.settings.encoding == 'h264' ? 1 : 2;
              var sizeVideo = this.settings.size;

              //Attach to streaming plugin
              janus.attach({
                plugin: "janus.plugin.streaming",
                success: _.bind(function(pluginHandle) {
                  this.streamingPlugIn = pluginHandle;

                  this.streamingPlugIn.oncleanup = _.bind(function(){
                    var body =
                    this.streamingPlugIn.send({
                      message: { "request": "destroy", "id": pluginHandle.session.getSessionId() },
                      success: _.bind(function() {

                        $.ajax({
                          url: API_BASEURL + "camera/peer-session",
                          type: "DELETE",
                          dataType: "json",
                          contentType: "application/json; charset=UTF-8",
                          data: JSON.stringify({
                            sessionId: AP_SESSION_ID
                          })
                        })
                          .done(_.bind(function(){
                            janus.sessionId = null;
                            this.setState('ready');

                            if (this.stoppingPromise) {
                              this.stoppingPromise.resolve();
                              this.stoppingPromise = null;
                            }
                          },this))
                          .always(_.bind(function(){
                            this.initJanus()
                          }, this))
                          .fail(_.bind(function(){
                            this.setState('error');
                            if (this.stoppingPromise) {
                              this.stoppingPromise.reject();
                              this.stoppingPromise = null;
                            }
                          },this));

                      }, this),
                      error: function(){
                        this.initJanus();
                        this.setState('error');
                        if (this.stoppingPromise) {
                          this.stoppingPromise.reject();
                          this.stoppingPromise = null;
                        }
                      }
                    });
                  },this);

                  var body = { "request": "watch", id: selectedStream };
                  this.streamingPlugIn.send({"message": body});
                },this),
                error: function(error) {
                  console.error(error);
                  noty({text: "Error communicating with the WebRTC system.", timeout: 3000});
                },
                onmessage: _.bind(function(msg, jsep) {
                  //console.log(" ::: Got a message :::");
                  //console.log(JSON.stringify(msg));
                  var result = msg["result"];
                    if(result !== null && result !== undefined) {
                      if(result["status"] !== undefined && result["status"] !== null) {
                        var status = result["status"];
                        if(status === 'stopped')
                          this.stopStreaming();
                      }
                    } else if(msg["error"] !== undefined && msg["error"] !== null) {
                      console.error(msg["error"]);
                      noty({text: "Unable to communicate with the camera.", timeout: 3000});
                      this.stopStreaming();
                      return;
                    }
                    if(jsep !== undefined && jsep !== null) {
                      //Answer
                      this.streamingPlugIn.createAnswer({
                        jsep: jsep,
                        media: { audioSend: false, videoSend: false },  // We want recvonly audio/video
                        success: _.bind(function(jsep) {
                          var body = { "request": "start" };
                          this.streamingPlugIn.send({"message": body, "jsep": jsep});
                        },this),
                        error: _.bind(function(error) {
                          console.error(error);
                          this.setState('error');
                        },this)
                      });
                    }
                }, this),
                onremotestream: _.bind(function(stream) {
                  //Starts GStreamer
                  $.ajax({
                    url: API_BASEURL + "camera/start-streaming",
                    type: "POST"
                  }).fail(_.bind(function(){
                    this.setState('error');
                  },this));

                  this.timeoutPlayingManager = window.setTimeout(_.bind(function(){
                    if(!isPlaying){
                      this.stopStreaming();
                      this.setState('error');
                      promise.reject();
                      clearTimeout(this.timeoutPlayingManager);                 }
                  },this),40000);

                  var isPlaying = false;

                  onPlay = _.bind(function () {
                    this.setState('streaming');
                    isPlaying = true;
                    this.activateWindowHideListener();
                    videoCont.off('canplaythrough', onPlay);
                    promise.resolve();
                  }, this);

                  videoCont.on("canplaythrough", onPlay);
                  videoCont.get(0).srcObject = stream;

                  app.eventManager.on('astrobox:videoStreamingEvent', this.manageVideoStreamingEvent, this);

                  this.streamingPlugIn.send({"message": { "request": "watch", id: this.settings.encoding == 'h264' ? 1 : 2, refresh: true }});
                },this),
                oncleanup: function() {
                  Janus.log(" ::: Got a cleanup notification :::");
                }
              });
              },this)
            );
          }, this),
          error: _.bind(function(error) {
            if(!this.$el.hasClass('ready')
              && !this.videoStreamingError //prevent if internal gstreamer error is showing
              && !this.stoppingPromise
              ){
                console.error(error);
                noty({text: "Unable to start the WebRTC session.", timeout: 3000});
                //This is a fatal error. The application can't recover. We should probably show an error state in the app.
                streamingState = 'stopped';
                this.setState('error');
              }

            promise.resolve();
          },this),
          destroyed: _.bind(this.initJanus, this)
        });
      }

      promise.resolve(); //We didn't start it but it wasn't visible anyway
    },this))
    .fail(_.bind(function(error){
      noty({text: "Unable to start the WebRTC system.", timeout: 3000});
      this.initJanus();
      promise.resolve();
    }, this));

    return promise;
  },
  stopStreaming: function()
  {
    var promise = $.Deferred();
    clearTimeout(this.timeoutPlayingManager);

    if (this.streaming && this.streamingPlugIn) {
      this.stoppingPromise = null;
      this.streamingPlugIn.send(
        {
          message: { "request": "stop" },
          success: _.bind(function() {
            this.stoppingPromise = promise;
          }, this),
          error: function(error){
            promise.reject(error);
          }
        }
      );
    } else {
      promise.resolve();
    }

    return promise;
  }
});

var CameraControlViewMac = CameraControlView.extend({
  canStream: true,
  startStreaming: function()
  {
    var promise = $.Deferred();

    this.setState('preparing');

    setTimeout(_.bind(function(){
      this.setState('streaming');
      promise.resolve();
    }, this), 1000);

    return promise;
  },
  stopStreaming: function()
  {
    this.setState('ready');
    return $.Deferred().resolve();
  }
});

var CameraViewBase = {
  mjpeg: CameraControlViewMJPEG,
  gstreamer: CameraControlViewWebRTC,
  mac: CameraControlViewMac
}[CAMERA_MANAGER];
