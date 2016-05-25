var CameraViewBase = CameraControlViewMJPEG

var CameraView = CameraViewBase.extend({
  el: '#camera-view',
  template: _.template( $("#camera-watch-page-template").html() ),
  serverUrl: null,
  events: {
	   'hide':'onHide',
     'show':'onShow',
     'click .buttons .columns .success': 'buttonEvent',
     'click .buttons .columns .secondary': 'buttonEvent',
     'click .buttons .columns .photo': 'buttonEvent',
     "change input[name='camera-mode']": 'cameraModeChanged'
  },
  manageVideoStreamingEvent: function(value)
  {
    this.onHide();//re-used function
    this.videoStreamingError = value.message;
    this.render();
  }
});
