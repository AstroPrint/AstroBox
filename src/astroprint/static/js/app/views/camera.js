var CameraView = CameraControlView.extend({
  el: '#camera-view',
  template: _.template( $("#camera-watch-page-template").html() ),
  serverUrl: null,
  events: {
	   'hide':'onHide',
     'show':'onShow',
     'click .buttons .columns .success': 'buttonEvent',
     'click .buttons .columns .secondary': 'buttonEvent',
     'click .buttons .columns .photo': 'buttonEvent',
     "change input[name='camera-mode']": 'cameraModeChanged',
  },
  subviews: null,
  render: function() {
	  this.$el.html(this.template());
  },
  onShow: function(){
    this.initialize();
  },
  onHide: function(){
    if(this.cameraMode == 'video'){
 	    if(this.state == 'streaming'){
        this.stopStreaming();
      }
    } else { 
      this.$('.camera-image').removeAttr('src');
    }
  }
});
