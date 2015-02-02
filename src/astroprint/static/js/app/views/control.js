/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var TempBarVerticalView = TempBarView.extend({
	containerDimensions: null,
	scale: null,
	type: null,
	dragging: false,
	events: _.extend(TempBarView.prototype.events, {
		'click .temp-bar': 'onClicked',
		'click button.temp-off': 'turnOff'
	}),
	setHandle: function(value) {
		if (!this.dragging) {
			var position = this._temp2px(value);
			var handle = this.$el.find('.temp-target');

			handle.css({transition: 'top 0.5s'});
			handle.css({top: position + 'px'});
			handle.text(value);
			setTimeout(function() {
				handle.css({transition: ''});
			}, 800);
		}
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
    onClicked: function(e) {
        e.preventDefault();

        var target = this.$el.find('.temp-target');

		var newTop = e.pageY - this.containerDimensions.top - target.innerHeight()/2.0;
		newTop = Math.min( Math.max(newTop, 0), this.containerDimensions.maxTop );

        var temp = this._px2temp(newTop);

        this.setHandle(temp);
        this._sendToolCommand('target', this.type, temp);
    },
	onResize: function() {
		var container = this.$el.find('.temp-bar');
		var handle = container.find('.temp-target');
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
	renderTemps: function(actual, target) {
		var handleHeight = this.$el.find('.temp-target').innerHeight();

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
	}
});

var TempView = Backbone.View.extend({
	el: '#temp-control',
	nozzleTempBar: null,
	bedTempBar: null,
	initialize: function() {
		this.nozzleTempBar = new TempBarVerticalView({
			scale: [0, app.printerProfile.get('max_nozzle_temp')],
			el: this.$el.find('.temp-control-cont.nozzle'),
			type: 'tool0'
		});
		this.bedTempBar = new TempBarVerticalView({
			scale: [0, app.printerProfile.get('max_bed_temp')],
			el: this.$el.find('.temp-control-cont.bed'),
			type: 'bed'
		});
	},
	render: function()
	{
        var profile = app.printerProfile.toJSON();

		this.nozzleTempBar.setMax(profile.max_nozzle_temp);

		if (profile.heated_bed) {
			this.bedTempBar.setMax(profile.max_bed_temp);
			this.bedTempBar.$el.removeClass('disabled');
		} else {
			this.bedTempBar.$el.addClass('disabled');
		}
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
		if (!app.socketData.get('paused')) {
			this.sendHomeCommand(['x', 'y']);
		}
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
		if (!app.socketData.get('paused')) {
			this.sendHomeCommand('z');
		}
	}
});

var ExtrusionControlView = Backbone.View.extend({
	el: '#extrusion-control',
	template: null,
	initialize: function() {
		this.template = _.template( this.$("#extruder-switch-template").html() );
	},
	render: function() {
		var printer_profile = app.printerProfile.toJSON();

		this.$('.row.extruder-switch').html(this.template({ 
			profile: printer_profile
		}));

		var events = {
			'click .extrude': 'extrudeTapped',
			'click .retract': 'retractTapped',
			'change .extrusion-length': 'lengthChanged'
		};

		if (printer_profile.extruder_count > 1) {
			events['change .extruder-number'] = "extruderChanged";
		}

		this.delegateEvents(events);
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
	lengthChanged: function(e) {
		var elem = $(e.target);

		if (elem.val() == 'other') {
			elem.addClass('hide');
			this.$('.other').removeClass('hide').focus();
			this.$('.other').focus();
		} else {
			this.$('input[name="extrusion-length"]').val(elem.val());
		}
	},
	extruderChanged: function(e) {
		this._sendChangeToolCommand($(e.target).val())
	},
	_sendChangeToolCommand: function(tool)
	{
        var data = {
            command: "select",
            tool: 'tool'+tool
        }

        $.ajax({
            url: API_BASEURL + "printer/tool",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data)
        });			
	},
	_checkAmount: function() {
		return !isNaN(this.$el.find('input[name="extrusion-length"]').val()); 
	},
	_sendExtrusionCommand: function(direction) {
        var data = {
            command: "extrude",
            amount: this.$el.find('input[name="extrusion-length"]').val() * direction
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

var FanControlView = Backbone.View.extend({
	el: '#temp-control .fan-control',
	events: {
		'click button.fan-on': "fanOn",
		'click button.fan-off': "fanOff"
	},
	fanOn: function()
	{
		this._setFanSpeed(255);
		this.$('.fan_icon').addClass('animate-spin');
	},
	fanOff: function()
	{
		this._setFanSpeed(0);
		this.$('.fan_icon').removeClass('animate-spin');
	},
	_setFanSpeed: function(speed)
	{
        var data = {
            command: "M106 S"+speed,
        }

        $.ajax({
            url: API_BASEURL + "printer/command",
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
	fanView: null,
	initialize: function() {
		this.tempView = new TempView();
		this.distanceControl = new DistanceControl();
		this.xyControlView = new XYControlView({distanceControl: this.distanceControl});
		this.zControlView = new ZControlView({distanceControl: this.distanceControl});
		this.extrusionView = new ExtrusionControlView();
		this.fanView = new FanControlView();

		this.listenTo(app.socketData, 'change:temps', this.updateTemps);
	},
	updateTemps: function(s, value) {
		if (!this.$el.hasClass('hide')) {
			this.tempView.updateBars(value);
		}
	},
	render: function() {
		if (app.socketData.get('paused')) {
			this.$el.addClass('print-paused');
		} else {
			this.$el.removeClass('print-paused');
		}

		this.extrusionView.render();
		this.tempView.render();
	},
	resumePrinting: function(e) {
		app.router.printingView.togglePausePrint(e);
		app.showPrinting();
		this.$el.addClass('hide');
	}
});