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
		this.setHandle(0);
	},
	setHandle: function(value) {
		var position = this._temp2px(value);
		var handle = this.$el.find('.set-temp');

		handle.css({transition: 'top 0.5s'});
		handle.css({top: position + 'px'});
		handle.text(value);
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
	setTemps: function(actual, target) {
		this.setHandle(target);
		this.$el.find('.current-temp-top').html(Math.round(actual)+'&deg;');
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
	el: '#temp-control',
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
	},
	updateBars: function(value) {
		this.nozzleTempBar.setTemps(value.extruder.actual, value.extruder.target);
		this.bedTempBar.setTemps(value.bed.actual, value.bed.target);
	}
});

var MovementControlView = Backbone.View.extend({
    sendJogCommand: function(axis, multiplier, distance) {
        if (typeof distance === "undefined")
        	distance = 10;
        //    distance = $('#jog_distance button.active').data('distance');
        //if (self.settings.getPrinterInvertAxis(axis)) {
        //    multiplier *= -1;
        //}

        var data = {
            "command": "jog"
        }
        data[axis] = distance * multiplier;

        $.ajax({
            url: API_BASEURL + "printer/printhead",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data)
        });
    },
    sendHomeCommand: function(axis) {
    	var data = {
            "command": "home",
            "axes": axis
        }

        $.ajax({
            url: API_BASEURL + "printer/printhead",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data)
        });
    }
});

var XYControlView = MovementControlView.extend({
	el: '#xy-controls',
	events: {
		'click .control_btn_X_plus': 'xPlusTapped',
		'click .control_btn_X_minus': 'xMinusTapped',
		'click .control_btn_Y_plus': 'yPlusTapped',
		'click .control_btn_Y_minus': 'yMinusTapped',
		'click .home_z': 'homeTapped'
	},
	xPlusTapped: function() {
		this.sendJogCommand('x', 1);
	},
	xMinusTapped: function() {
		this.sendJogCommand('x', -1);
	},
	yPlusTapped: function() {
		this.sendJogCommand('y', 1);
	},
	yMinusTapped: function() {
		this.sendJogCommand('y', -1);
	},
	homeTapped: function() {
		this.sendHomeCommand(['x', 'y']);
	}
});

var ZControlView = MovementControlView.extend({
	el: '#z-controls',
	events: {
		'click .control_btn_Z_plus': 'zPlusTapped',
		'click .control_btn_Z_minus': 'zMinusTapped',
		'click .home_z': 'homeTapped'
	},
	zPlusTapped: function() {
		this.sendJogCommand('z', 1, 1);
	},
	zMinusTapped: function() {
		this.sendJogCommand('z', -1, 1);
	},
	homeTapped: function() {
		this.sendHomeCommand('z');
	}
});

var ControlView = Backbone.View.extend({
	tempView: new TempView(),
	xyControlView: new XYControlView(),
	zControlView: new ZControlView(),
	el: '#control-view',
	updateTemps: function(value) {
		this.tempView.updateBars(value);
	}
});