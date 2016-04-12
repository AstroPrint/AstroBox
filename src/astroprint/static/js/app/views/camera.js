var CameraView = CameraControlView.extend({
  el: '#camera-view',
  template: _.template( $("#camera-watch-page-template").html() ),
  serverUrl: null,
  events: {
	   'hide':'onHide',
     'show':'onShow',
     'click .buttons .columns .success': 'startStreaming',
     'click .buttons .columns .secondary': 'stopStreaming'
  },
  subviews: null,
  render: function() {
	  this.$el.html(this.template());
  },
  onShow: function(){
    this.render();
  },
  onHide: function(){
 	  this.stopStreaming();
  }
});
