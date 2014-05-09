var tempBarView = Backbone.View.extend({
	events: {
		'touchstart .set-temp': 'onTouchStart',
		'touchmove .set-temp': 'onTouchMove',
		'touchend .set-temp': 'onTouchEnd'
	},
	onTouchStart: function(e) {
		$(e.target).addClass('moving');
	},
	onTouchMove: function(e) {
		$(e.target).text(e.originalEvent.changedTouches[0].clientY);
	},
	onTouchEnd: function(e) {
		$(e.target).removeClass('moving');
	}
});

var TempView = Backbone.View.extend({
	nozzleTempBar: null,
	bedTempBar: null,
	initialize: function() {
		this.nozzleTempBar = new tempBarView({el: this.$el.find('.temp-control-cont.nozzle')});
		this.bedTempBar = new tempBarView({el: this.$el.find('.temp-control-cont.bed')});
	}
});

var ControlView = Backbone.View.extend({
	tempView: null,
	el: $('#control-view'),
	initialize: function() {
		this.tempView = new TempView({el: this.$el.find('#temp-control')});
	}
});