/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* global Janus */

/* exported CameraViewBase */

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
            .fail(_.bind(function(){
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
        .fail(_.bind(function(){
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

    var photoCont = this.getPhotoContainer();

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
      .done(_.bind(function(){
        this.streaming = true;
        var videoCont = this.getVideoContainer();
        videoCont.attr('src', '/webcam/?action=stream&time='+new Date().getTime());

        videoCont.on('load', _.bind(function() {
          this.setState('streaming');
          this.activateWindowHideListener();
          videoCont.off('load');
          promise.resolve();
        },this));

        videoCont.on('error', _.bind(function() {
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

var CameraControlViewGstreamer = CameraControlView.extend({
  canStream: true,
  managerName: 'gstreamer',
  startStreaming: function()
  {
    var promise = $.Deferred();

    this.setState('preparing');

    this.streaming = true;
    var videoCont = this.getVideoContainer();

    videoCont.on('load', _.bind(function(data) {
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

    videoCont.attr('src', 'video-stream');

    return promise;
  },
  stopStreaming: function()
  {
    var promise = $.Deferred();

    if (this.streaming){

      this.setState('ready');
      var videoCont = this.getVideoContainer();
      videoCont.off('load');
      videoCont.off('error');
      videoCont.removeAttr('src');
      promise.resolve();

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
  gstreamer: CameraControlViewGstreamer,
  mac: CameraControlViewMac
}[CAMERA_MANAGER];
