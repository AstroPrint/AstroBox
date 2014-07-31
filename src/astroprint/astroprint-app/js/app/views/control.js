/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var tempBarView = Backbone.View.extend({
	containerDimensions: null,
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
		'mouseout .temp-bar': 'onTouchEnd',
		'click .temp-bar': 'onClicked',
		'click button.temp-off': 'turnOff'
	},
	initialize: function(params) {
		this.scale = params.scale;
		this.type = params.type;
		$(window).bind("resize.app", _.bind(this.onResize, this));
	},
    remove: function() {
        $(window).unbind("resize.app");
        Backbone.View.prototype.remove.call(this);
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
			}, 800);
		}
	},
	onTouchStart: function(e) {
		e.preventDefault();
		this.dragging = true;
		$(e.target).addClass('moving');
	},
	onTouchMove: function(e) {
		if (this.dragging) {
			e.preventDefault();

			var target = $(e.target);

			if (e.type == 'mousemove') {
				var pageY = e.originalEvent.pageY;
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

		$(e.target).removeClass('moving');

		//Set it here
		this._sendToolCommand('target', this.type, this.$el.find('.set-temp').text());

		this.dragging = false;
	},
    onClicked: function(e) {
        e.preventDefault();

        var target = this.$el.find('.set-temp');

		var newTop = e.pageY - this.containerDimensions.top - target.innerHeight()/2.0;
		newTop = Math.min( Math.max(newTop, 0), this.containerDimensions.maxTop );

        var temp = this._px2temp(newTop);

        this.setHandle(temp);
        this._sendToolCommand('target', this.type, temp);
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

		this.setHandle(Math.min(Math.round(target), this.scale[1]));
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

        if (temp === null) {
        	temp = 0;
        }

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
	resetBars: function() {
		this.nozzleTempBar.onResize();
		this.bedTempBar.onResize();
	},
	updateBars: function(value) {
		this.nozzleTempBar.setTemps(value.extruder.actual, value.extruder.target);
		this.bedTempBar.setTemps(value.bed.actual, value.bed.target);
	}
});

var DistanceControl = Backbone.View.extend({
	el: '#distance-control',
	selected: 10,
	events: {
		'click button': 'selectDistance'
	},
	selectDistance: function(e) {
		var el = $(e.currentTarget);
		this.$el.find('.success').removeClass('success').addClass('secondary');
		el.addClass('success').removeClass('secondary');
		this.selected = el.attr('data-value');
	}
});

var MovementControlView = Backbone.View.extend({
	distanceControl: null,
	initialize: function(params) {
		this.distanceControl = params.distanceControl;
	},
    sendJogCommand: function(axis, multiplier, distance) {
        if (typeof distance === "undefined")
        	distance = 10;

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
		'click .control_btn_x_plus': 'xPlusTapped',
		'click .control_btn_x_minus': 'xMinusTapped',
		'click .control_btn_y_plus': 'yPlusTapped',
		'click .control_btn_y_minus': 'yMinusTapped',
		'click .home_z': 'homeTapped'
	},
	xPlusTapped: function() {
		this.sendJogCommand('x', 1, this.distanceControl.selected);
	},
	xMinusTapped: function() {
		this.sendJogCommand('x', -1, this.distanceControl.selected);
	},
	yPlusTapped: function() {
		this.sendJogCommand('y', 1, this.distanceControl.selected);
	},
	yMinusTapped: function() {
		this.sendJogCommand('y', -1, this.distanceControl.selected);
	},
	homeTapped: function() {
		this.sendHomeCommand(['x', 'y']);
	}
});

var ZControlView = MovementControlView.extend({
	el: '#z-controls',
	events: {
		'click .control_btn_z_plus': 'zPlusTapped',
		'click .control_btn_z_minus': 'zMinusTapped',
		'click .home_z': 'homeTapped'
	},
	zPlusTapped: function() {
		this.sendJogCommand('z', 1, this.distanceControl.selected);
	},
	zMinusTapped: function() {
		this.sendJogCommand('z', -1, this.distanceControl.selected);
	},
	homeTapped: function() {
		this.sendHomeCommand('z');
	}
});

var ExtrusionControlView = Backbone.View.extend({
	el: '#extrusion-control',
	events: {
		'click .extrude': 'extrudeTapped',
		'click .retract': 'retractTapped'
	},
	extrudeTapped: function() {
		if (this._checkAmount()) {
			this._sendExtrusionCommand(1);
		}
	},
	retractTapped: function() {
		if (this._checkAmount()) {
			this._sendExtrusionCommand(-1);
		}
	},
	_checkAmount: function() {
		return !isNaN(this.$el.find('.amount-field').val()); 
	},
	_sendExtrusionCommand: function(direction) {
        var data = {
            command: "extrude",
            amount: this.$el.find('.amount-field').val() * direction
        }

        $.ajax({
            url: API_BASEURL + "printer/tool",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data)
        });		
	}
});

var ControlView = Backbone.View.extend({
	el: '#control-view',
	events: {
		'click .back-to-print button': 'resumePrinting',
		'show': 'render'
	},
	tempView: null,
	distanceControl: null,
	xyControlView: null,
	zControlView: null,
	extrusionView: null,
	initialize: function(params) {
		this.tempView = new TempView();
		this.distanceControl = new DistanceControl();
		this.listenTo(params.app.socketData, 'change:temps', this.updateTemps);
		this.xyControlView = new XYControlView({distanceControl: this.distanceControl});
		this.zControlView = new ZControlView({distanceControl: this.distanceControl});
		this.extrusionView = new ExtrusionControlView();
	},
	updateTemps: function(s, value) {
		if (!this.$el.hasClass('hide')) {
			this.tempView.updateBars(value);
		}
	},
	render: function() {
		if (app.socketData.get('paused')) {
			this.$el.find('.back-to-print .filename').text(app.socketData.get('printing_progress').filename);
			this.$el.find('.back-to-print').show();
		} else {
			this.$el.find('.back-to-print').hide();
		}
	},
	resumePrinting: function() {
		app.printingView.togglePausePrint();
		app.showPrinting();
		this.$el.addClass('hide');
	}
});