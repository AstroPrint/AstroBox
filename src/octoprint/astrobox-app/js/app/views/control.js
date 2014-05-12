var tempBarView = Backbone.View.extend({
	containerDimensions: null,
	handleTop: null,
	scale: null,
	type: null,
	dragging: false,
	events: {
		'touchstart .set-temp': 'onTouchStart',
		'mousedown .set-temp': 'onTouchStart',
		'touchmove .set-temp': 'onTouchMove',
		'mousemove .set-temp': 'onTouchMove',
		'touchend .set-temp': 'onTouchEnd',
		'mouseup .set-temp': 'onTouchEnd',
		'mouseout .set-temp': 'onTouchEnd',
		'resize': 'onResize',
		'click button.temp-off': 'turnOff'
	},
	initialize: function(params) {
		this.scale = params.scale;
		this.type = params.type;
		this.onResize();
	},
	turnOff: function(e) {
		this._sendToolCommand('target', this.type, 0);
		this.setHandle(0);
	},
	setHandle: function(value) {
		if (!this.dragging) {
			var position = this._temp2px(value);
			var handle = this.$el.find('.set-temp');

			handle.css({transition: 'top 0.5s'});
			handle.css({top: position + 'px'});
			handle.text(value);
			setTimeout(function() {
				handle.css({transition: ''});
			}, 500);
		}
	},
	onTouchStart: function(e) {
		e.preventDefault();

		this.dragging = true;

		var target = $(e.target);

		this.handleTop = target.position().top;

		target.addClass('moving');
	},
	onTouchMove: function(e) {
		if (this.dragging) {
			e.preventDefault();

			var target = $(e.target);

			if (e.type == 'mousemove') {
				var pageY = e.originalEvent.pageY 
			} else {
				var pageY = e.originalEvent.changedTouches[0].clientY;
			}

			var newTop = pageY - this.containerDimensions.top - target.innerHeight()/2.0;
			newTop = Math.min(Math.max(newTop, 0), this.containerDimensions.maxTop );

			target.css({top: newTop+'px'});

			target.text(this._px2temp(newTop));
		}
	},
	onTouchEnd: function(e) {
		e.preventDefault();

		this.handleTop = null;

		$(e.target).removeClass('moving');

		//Set it here
		this._sendToolCommand('target', this.type, this.$el.find('.set-temp').text());

		this.dragging = false;
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
		var handleHeight = this.$el.find('.set-temp').innerHeight();

		this.setHandle(target);
		this.$el.find('.current-temp-top').html(Math.round(actual)+'&deg;');
		this.$el.find('.current-temp').css({top: (this._temp2px(actual) + handleHeight/2 )+'px'});
	},
	_temp2px: function(temp) {
		var px = temp * this.containerDimensions.px4degree;

		return this.containerDimensions.maxTop - px;
	},
	_px2temp: function(px) {
		return Math.round( ( (this.containerDimensions.maxTop - px) / this.containerDimensions.px4degree ) );
	},
    _sendToolCommand: function(command, type, temp, successCb, errorCb) {
        var data = {
            command: command
        };

        var endpoint;
        if (type == "bed") {
            if ("target" == command) {
                data["target"] = parseInt(temp);
            } else if ("offset" == command) {
                data["offset"] = parseInt(temp);
            } else {
                return;
            }

            endpoint = "bed";
        } else {
            var group;
            if ("target" == command) {
                group = "targets";
            } else if ("offset" == command) {
                group = "offsets";
            } else {
                return;
            }
            data[group] = {};
            data[group][type] = parseInt(temp);

            endpoint = "tool";
        }

        $.ajax({
            url: API_BASEURL + "printer/" + endpoint,
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data),
            success: function() { if (successCb !== undefined) successCb(); },
            error: function() { if (errorCb !== undefined) errorCb(); }
        });
    }
});

var TempView = Backbone.View.extend({
	el: '#temp-control',
	nozzleTempBar: null,
	bedTempBar: null,
	initialize: function() {
		this.nozzleTempBar = new tempBarView({
			scale: [0, 280],
			el: this.$el.find('.temp-control-cont.nozzle'),
			type: 'tool0'
		});
		this.bedTempBar = new tempBarView({
			scale: [0, 120],
			el: this.$el.find('.temp-control-cont.bed'),
			type: 'bed'
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