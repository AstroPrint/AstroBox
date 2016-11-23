var CameraView = CameraViewBase.extend({
  el: '#camera-view',
  template: _.template( $("#camera-watch-page-template").html() ),
  serverUrl: null,
  events: {
	   'hide':'onHide',
     'show':'onShow',
     'click .buttons .columns button': 'onCameraBtnClicked',
     "change #camera-mode-camera": 'cameraModeChanged'
  },
  manageVideoStreamingEvent: function(value)
  {
    this.onHide();//re-used function
    this.videoStreamingError = value.message;

    if(value.message.indexOf('camera settings have been changed') > -1){
      this.videoStreamingErrorTitle = 'Camera settings changed'
    } else {
      this.videoStreamingErrorTitle = null;
    }
    this.render();
  },
  onCameraBtnClicked: function(e)
  {
    e.preventDefault();

    var target = $(e.currentTarget);
    var loadingBtn = target.closest('.loading-button');

    $('.camera-screen').hide();
    loadingBtn.addClass('loading');

    this.buttonEvent()
      .fail(function(){
        $('.camera-screen').show();
        noty({text: "Camera error.", timeout: 3000});
      })
      .always(function(){
        loadingBtn.removeClass('loading');
      });
  },
  getPhotoContainer: function()
  {
    return this.$('.camera-image');
  },
  getVideoContainer: function()
  {
    return this.$('#video-stream');
  }
});
