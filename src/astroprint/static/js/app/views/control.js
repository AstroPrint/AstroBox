/*
 *  (c) 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */
var ControlTempView = Backbone.View.extend({
  className: 'control-temps small-12 columns',
  el: '#temp-control-template',
  semiCircleTemp_views: {},
  extruders_count: null,
  initialize: function()
  {
    /* Change default circle for semi circle*/
    // Arc layout
    $.circleProgress.defaults.arcCoef = 0.5; // range: 0..1
    $.circleProgress.defaults.startAngle = 0.5 * Math.PI;

    $.circleProgress.defaults.drawArc = function (v) {
      var ctx = this.ctx,
        r = this.radius,
        t = this.getThickness(),
        c = this.arcCoef,
        a = this.startAngle + (1 - c) * Math.PI;

      v = Math.max(0, Math.min(1, v));

      ctx.save();
      ctx.beginPath();

      if (!this.reverse) {
        ctx.arc(r, r, r - t / 2, a, a + 2 * c * Math.PI * v);
      } else {
        ctx.arc(r, r, r - t / 2, a + 2 * c * Math.PI, a + 2 * c * (1 - v) * Math.PI, a);
      }

      ctx.lineWidth = t;
      ctx.lineCap = this.lineCap;
      ctx.strokeStyle = this.arcFill;
      ctx.stroke();
      ctx.restore();
    };

    $.circleProgress.defaults.drawEmptyArc = function (v) {
      var ctx = this.ctx,
        r = this.radius,
        t = this.getThickness(),
        c = this.arcCoef,
        a = this.startAngle + (1 - c) * Math.PI;

      v = Math.max(0, Math.min(1, v));

      if (v < 1) {
        ctx.save();
        ctx.beginPath();

        if (v <= 0) {
          ctx.arc(r, r, r - t / 2, a, a + 2 * c * Math.PI);
        } else {
          if (!this.reverse) {
            ctx.arc(r, r, r - t / 2, a + 2 * c * Math.PI * v, a + 2 * c * Math.PI);
          } else {
            ctx.arc(r, r, r - t / 2, a, a + 2 * c * (1 - v) * Math.PI);
          }
        }

        ctx.lineWidth = t;

        ctx.strokeStyle = this.emptyFill;
        ctx.stroke();
        ctx.restore();
      }
    };
    /* End semicircle*/

    this.extruders_count = (app.printerProfile.toJSON()).extruder_count;

    var semiCircleTemp = null;
    this.$el.empty();

    var initialsTemps = app.socketData.attributes.temps;

    //extruders
    for (var i = 0; i < this.extruders_count; i++) {

      semiCircleTemp = new SemiCircleTempView({'tool': i, 'temps': initialsTemps['extruders'][i]});
      this.semiCircleTemp_views[i] = semiCircleTemp;
      this.$el.prepend(semiCircleTemp.render().el);
    }
    //bed
    semiCircleTemp = new SemiCircleTempView({'tool': null, 'temps': initialsTemps['bed']});
    this.semiCircleTemp_views[this.extruders_count] = semiCircleTemp;
    this.$el.prepend(semiCircleTemp.render().el);
  },
  updateTemps: function(value) {
    var temps = {};
    for (var i = 0; i < Object.keys(this.semiCircleTemp_views).length; i++) {
      if (this.semiCircleTemp_views[i].el.id == 'bed' ) {
        temps = {'current': value.bed.actual, 'target': value.bed.target};
      } else {
        temps = {'current': value.extruders[i].current, 'target': value.extruders[i].target};
      }
      (this.semiCircleTemp_views[i]).updateValues(temps);
    }
  }
});
var SemiCircleTempView = Backbone.View.extend({
  className: 'semi-circle-temps small-12 columns',
  folder: null,
  template: _.template( $("#semi-circle-template").html() ),
  initialize: function(params)
  {
    var tool = params.tool;

    if (tool != null) {
      this.$el.attr('id', 'tool'+tool);
    } else {
      this.$el.attr('id', 'bed');
    }

    if (this.el.id == 'bed') {
      console.log("cama caliente",(app.printerProfile.toJSON()).heated_bed);
      if ((app.printerProfile.toJSON()).heated_bed) {
        $("#"+ this.el.id).circleProgress({ value: Math.round((params.temps.actual / app.printerProfile.get('max_bed_temp')) * 100) / 100 });
        this.$el.removeClass('disabled');
      } else {
        this.$el.addClass('disabled');
      }
    } else {
      $("#"+ this.el.id).circleProgress({ value: Math.round((params.temps.actual / app.printerProfile.get('max_nozzle_temp')) * 100) / 100 });
    }
  },
  render: function ()
  {
    this.$el.empty();
    this.$el.html( this.template( { } ) );

    $("#"+ this.el.id).circleProgress({
      arcCoef: 0.55,
      size: 180,
      thickness: 20,
      fill: { gradient: ['#60D2E5', '#E8A13A', '#F02E19'] }
    });

    //this.updateValues();
    return this;
  },
  updateValues: function (temps)
  {
    $("#"+ this.el.id).circleProgress({ value: Math.round((temps.current / app.printerProfile.get('max_nozzle_temp')) * 100) / 100 });
  }
});

var TempBarVerticalView = TempBarView.extend({
  containerDimensions: null,
  scale: null,
  type: null,
  dragging: false,
  events: _.extend(TempBarView.prototype.events, {
    'click .temp-bar': 'onClicked',
    'click button.temp-off': 'turnOff'
  }),
  setHandle: function(value)
  {
    if (!this.dragging) {
      var position = this._temp2px(value);
      var handle = this.$el.find('.temp-target');

      handle.css({transition: 'top 0.5s'});
      handle.css({top: position + 'px'});
      handle.find('span.target-value').text(value);
      setTimeout(function() {
        handle.css({transition: ''});
      }, 800);
    }
  },
  onTouchMove: function(e)
  {
    if (this.dragging) {
      e.preventDefault();
      e.stopPropagation();
      var target = this.$('.temp-target');

      if (e.type == 'mousemove') {
        var pageY = e.originalEvent.pageY;
      } else {
        var pageY = e.originalEvent.changedTouches[0].clientY + $(document).scrollTop();
      }

      var newTop = pageY - this.containerDimensions.top - target.innerHeight()/2.0;

      newTop = Math.min(Math.max(newTop, 0), this.containerDimensions.maxTop );

      target.css({top: newTop+'px'});
      target.find('span.target-value').text(this._px2temp(newTop));
    }
  },
  onClicked: function(e)
  {
    e.preventDefault();
    var target = this.$el.find('.temp-target');
    var newTop = e.pageY - this.containerDimensions.top - target.innerHeight()/2.0;

    newTop = Math.min( Math.max(newTop, 0), this.containerDimensions.maxTop );

    var temp = this._px2temp(newTop);

    this.setHandle(temp);
    this._sendToolCommand('target', this.type, temp);
  },
  onResize: function()
  {
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
  renderTemps: function(actual, target)
  {
    var handleHeight = this.$el.find('.temp-target').innerHeight();

    if (actual !== null) {
      this.$el.find('.current-temp-top').html(Math.round(actual)+'&deg;');
      this.$el.find('.current-temp').css({top: (this._temp2px(actual) + handleHeight/2 )+'px'});
    }

    if (target !== null) {
      this.setHandle(Math.min(Math.round(target), this.scale[1]));
    }
  },
  _temp2px: function(temp)
  {
    var px = temp * this.containerDimensions.px4degree;

    return this.containerDimensions.maxTop - px;
  },
  _px2temp: function(px)
  {
    return Math.round( ( (this.containerDimensions.maxTop - px) / this.containerDimensions.px4degree ) );
  }
});

var TempView = Backbone.View.extend({
  el: '#temp-control',
  nozzleTempBar: null,
  bedTempBar: null,
  initialize: function()
  {
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
  resetBars: function()
  {
    this.nozzleTempBar.onResize();
    this.bedTempBar.onResize();
  },
  updateBars: function(value)
  {
    if (value.extruder) {
      this.nozzleTempBar.setTemps(value.extruder.actual, value.extruder.target);
    }

    if (value.bed) {
      this.bedTempBar.setTemps(value.bed.actual, value.bed.target);
    }
  }
});

var DistanceControl = Backbone.View.extend({
  el: '#distance-control',
  selected: 10,
  events: {
    'click button': 'selectDistance'
  },
  selectDistance: function(e)
  {
    var el = $(e.currentTarget);
    this.$el.find('.success').removeClass('success').addClass('secondary');
    el.addClass('success').removeClass('secondary');
    this.selected = el.attr('data-value');
  }
});

var MovementControlView = Backbone.View.extend({
  distanceControl: null,
  printerProfile: null,
  initialize: function(params)
  {
    this.distanceControl = params.distanceControl;
  },
  sendJogCommand: function(axis, multiplier, distance)
  {
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
  sendHomeCommand: function(axis)
  {
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
  xPlusTapped: function()
  {
    this.sendJogCommand('x', 1, this.distanceControl.selected);
  },
  xMinusTapped: function()
  {
    this.sendJogCommand('x', -1, this.distanceControl.selected);
  },
  yPlusTapped: function()
  {
    this.sendJogCommand('y', 1, this.distanceControl.selected);
  },
  yMinusTapped: function()
  {
    this.sendJogCommand('y', -1, this.distanceControl.selected);
  },
  homeTapped: function()
  {
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
  zPlusTapped: function()
  {
    this.sendJogCommand('z', 1, this.distanceControl.selected);
  },
  zMinusTapped: function()
  {
    this.sendJogCommand('z', -1 , this.distanceControl.selected);
  },
  homeTapped: function()
  {
    if (!app.socketData.get('paused')) {
      this.sendHomeCommand('z');
    }
  }
});

var ExtrusionControlView = Backbone.View.extend({
  el: '#extrusion-control',
  template: null,
  events: {
    'click .extrude': 'extrudeTapped',
    'click .retract': 'retractTapped',
    'change .extrusion-length': 'lengthChanged',
    'change .extrusion-speed': 'speedChanged',
    'keydown input.back-to-select': 'onKeyDownBackToSelect'
  },
  initialize: function()
  {
    this.template = _.template( this.$("#extruder-switch-template").html() );
  },
  render: function()
  {
    var printer_profile = app.printerProfile.toJSON();

    this.$('.row.extruder-switch').html(this.template({
      profile: printer_profile
    }));

    if (printer_profile.extruder_count > 1) {
      this.events['change .extruder-number'] = "extruderChanged";
    }

    this.delegateEvents(this.events);
  },
  extrudeTapped: function()
  {
    if (this._checkAmount()) {
      this._sendExtrusionCommand(1);
    }
  },
  retractTapped: function()
  {
    if (this._checkAmount()) {
      this._sendExtrusionCommand(-1);
    }
  },
  lengthChanged: function(e)
  {
    var elem = $(e.target);

    if (elem.val() == 'other') {
      elem.addClass('hide');
      this.$('.other-length').removeClass('hide').find('input').focus().select();
    } else {
      this.$('input[name="extrusion-length"]').val(elem.val());
    }
  },
  speedChanged: function(e)
  {
    var elem = $(e.target);

    if (elem.val() == 'other') {
      elem.addClass('hide');
      this.$('.other-speed').removeClass('hide').find('input').focus().select();
    } else {
      this.$('input[name="extrusion-speed"]').val(elem.val());
    }
  },
  extruderChanged: function(e)
  {
    this._sendChangeToolCommand($(e.target).val())
  },
  onKeyDownBackToSelect: function(e)
  {
    if (e.keyCode == 27) { //ESC Key
      var target = $(e.currentTarget);
      var select = target.closest('div.select-with-text').find('select');

      //Find out the default value. Middle one
      var defaultValue = select.find('option[default]').val();

      target.closest('.row').addClass('hide');
      target.val(defaultValue);
      select.removeClass('hide').val(defaultValue);
    }
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
  _checkAmount: function()
  {
    return !isNaN(this.$el.find('input[name="extrusion-length"]').val());
  },
  _sendExtrusionCommand: function(direction)
  {
    var data = {
      command: "extrude",
      amount: parseFloat(this.$('input[name="extrusion-length"]').val() * direction),
      speed: parseFloat(this.$('input[name="extrusion-speed"]').val())
    }

    var extruder = this.$('select.extruder-number').val();

    if (extruder) {
      data['tool'] = 'tool'+extruder;
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
      command: "set",
      tool: 0,
      speed: speed
    }

    $.ajax({
      url: API_BASEURL + "printer/fan",
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
  prueba: null,
  initialize: function()
  {
    this.tempView = new TempView();
    this.distanceControl = new DistanceControl();
    this.xyControlView = new XYControlView({distanceControl: this.distanceControl});
    this.zControlView = new ZControlView({distanceControl: this.distanceControl});
    this.extrusionView = new ExtrusionControlView();
    this.fanView = new FanControlView();
    this.prueba = new ControlTempView();

    this.listenTo(app.socketData, 'change:temps', this.updateTemps);
    this.listenTo(app.socketData, 'change:paused', this.onPausedChanged);
  },
  updateTemps: function(s, value)
  {
    console.log("value", value)
    if (!this.$el.hasClass('hide')) {
      this.prueba.updateTemps(value);
      //this.tempView.updateBars(value);
    }
  },
  render: function()
  {
    this.onPausedChanged(app.socketData, app.socketData.get('paused'));

    this.extrusionView.render();
    this.tempView.render();
    this.prueba.render();
  },
  resumePrinting: function(e)
  {
    app.setPrinting();
    app.router.navigate("printing", {replace: true, trigger: true});
    app.router.printingView.togglePausePrint(e);

    this.$el.addClass('hide');
  },
  onPrintingProgressChanged: function(model, printingProgress)
  {
    var el = this.$('.back-to-print .filename');

    if (printingProgress && printingProgress.printFileName && printingProgress.printFileName != el.text()) {
      el.text(printingProgress.printFileName)
    }
  },
  onPausedChanged: function(model, paused)
  {
    if (paused) {
      this.listenTo(app.socketData, 'change:printing_progress', this.onPrintingProgressChanged);
      this.$el.addClass('print-paused');
    } else {
      this.stopListening(app.socketData, 'change:printing_progress');

      if (app.socketData.get('printing')) {
        app.router.navigate("printing", {replace: true, trigger: true});
      } else {
        this.$el.removeClass('print-paused');
      }
    }
  }
});
