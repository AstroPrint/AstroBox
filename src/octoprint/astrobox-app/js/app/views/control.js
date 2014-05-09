var tempBarView = Backbone.View.extend({
	containerDimensions: null,
	handleTop: null,
	scale: null,
	events: {
		'touchstart .set-temp': 'onTouchStart',
		'touchmove .set-temp': 'onTouchMove',
		'touchend .set-temp': 'onTouchEnd',
		'resize': 'onResize',
		'click button.temp-off': 'turnOff'
	},
	initialize: function(params) {
		this.scale = params.scale;
		this.onResize();
	},
	turnOff: function(e) {
		var position = this._temp2px(0);
		var handle = this.$el.find('.set-temp');

		handle.css({transition: 'top 0.5s'});
		handle.css({top: position + 'px'});
		handle.text('OFF');
		setTimeout(function() {
			handle.css({transition: ''});
		}, 500);
	},
	onTouchStart: function(e) {
		e.preventDefault();

		var target = $(e.target);

		this.handleTop = target.position().top;

		target.addClass('moving');
	},
	onTouchMove: function(e) {
		e.preventDefault();

		var target = $(e.target);

		var newTop = e.originalEvent.changedTouches[0].clientY - this.containerDimensions.top;
		newTop = Math.min(Math.max(newTop, 0), this.containerDimensions.maxTop );

		target.css({top: newTop+'px'});

		target.text(this._px2temp(newTop));
	},
	onTouchEnd: function(e) {
		e.preventDefault();

		this.handleTop = null;

		$(e.target).removeClass('moving');
	},
	onResize: function() {
		var container = this.$el.find('.temp-bar');
		var handle = container.find('.set-temp');
		var label = container.find('label');

		var height = container.height();
		var maxTop = height - handle.innerHeight() - label.innerHeight();

		this.containerDimensions = {
			top: container.offset().top,
			height: height,
			maxTop: maxTop,
			px4degree: maxTop / (this.scale[1] - this.scale[0])
		};
	},
	_temp2px: function(temp) {
		var px = temp * this.containerDimensions.px4degree;

		return this.containerDimensions.maxTop - px;
	},
	_px2temp: function(px) {
		return Math.round( ( (this.containerDimensions.maxTop - px) / this.containerDimensions.px4degree ) );
	}
});

var TempView = Backbone.View.extend({
	nozzleTempBar: null,
	bedTempBar: null,
	initialize: function() {
		this.nozzleTempBar = new tempBarView({
			scale: [0, 280],
			el: this.$el.find('.temp-control-cont.nozzle')
		});
		this.bedTempBar = new tempBarView({
			scale: [0, 120],
			el: this.$el.find('.temp-control-cont.bed')
		});
	}
});

var ControlView = Backbone.View.extend({
	tempView: null,
	el: $('#control-view'),
	initialize: function() {
		this.tempView = new TempView({el: this.$el.find('#temp-control')});
	}
});