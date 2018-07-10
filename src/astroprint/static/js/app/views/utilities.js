/*
 *  (c) 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */
var TempView = Backbone.View.extend({
  className: 'control-temps small-12 columns',
  el: '#temp-control-template',
  semiCircleTemp_views: {},
  navExtruders_views: {},
  extruders_count: null,
  socketTemps: null,
  heated_bed: null,
  temp_presets : null,
  events: {
    'click .nav-extruder': 'navExtruderClicked',
    'click .semi-circle-temps': 'semiCircleTempsClicked',
    'click .arrow': 'arrowClicked'
  },
  initialize: function()
  {
    new SemiCircleProgress();

    var profile = app.printerProfile.toJSON();
    this.extruders_count = profile.extruder_count;
    this.heated_bed = profile.heated_bed;
    this.temp_presets = profile.temp_presets;
    this.renderCircleTemps();
  },
  renderCircleTemps: function() {
    if (app.socketData.attributes.temps != this.socketTemps) {
      this.socketTemps = app.socketData.attributes.temps;
    }
    var temps = null;

    var semiCircleTemp = null;

    this.$el.find('#slider-nav').empty();
    this.$el.find('#slider').empty();
    this.$el.find('.bed').empty();


    for (var i = 0; i < this.extruders_count; i++) {
      semiCircleTemp = new TempSemiCircleView({'tool': i, enableOff: true});
      this.semiCircleTemp_views[i] = semiCircleTemp;
      this.$el.find('#slider').append(this.semiCircleTemp_views[i].render().el);

      if (this.socketTemps.lenght > 0) {
        temps = {current: this.socketTemps.extruders[i].current, target: this.socketTemps.extruders[i].target};
      } else {
        temps = {current: null, target: null};
      }
      this.semiCircleTemp_views[i].setTemps(temps.current, temps.target);

      //nav-extruders
      var tempId = "temp-" + i;

      this.navExtruders_views[i] = '<div class="nav-extruder'+ ((i == 0)? " current-slide" : "") + '" id='+ tempId +'><a class="extruder-number">' + (i+1) + '</a><span class="all-temps"></span></div>';
      this.$el.find('#slider-nav').append(this.navExtruders_views[i]);
    }

    //bed
    if (this.heated_bed) {
      this.$el.find('#bed-container').removeClass('no-bed');
    } else {
      this.$el.find('#bed-container').addClass('no-bed');
    }
    semiCircleTemp = new TempSemiCircleView({'tool': null, enableOff: true});
    this.semiCircleTemp_views[this.extruders_count] = semiCircleTemp;
    this.$el.find('.bed').append(this.semiCircleTemp_views[this.extruders_count].render().el);

    if (this.socketTemps.lenght > 0) {
      temps = {current: this.socketTemps.bed.current, target: this.socketTemps.bed.target};
    } else {
      temps = {current: null, target: null};
    }

    this.semiCircleTemp_views[this.extruders_count].setTemps(temps.current, temps.target);

    for (var i = 0; i <= this.extruders_count; i++) {
      this._setCircleProgress(i);
    }

    if (this.extruders_count > 4) {
      this.$el.find('#previous').removeClass('hide');
      this.$el.find('#next').removeClass('hide');
    }
    if (this.socketTemps.length > 0) {
      this.updateTemps(this.socketTemps);
    }
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

      if (this.semiCircleTemp_views[i].type == 'tool') {
        var search = '#temp-'+i;
        var tempValue = '- -';
        if (this.semiCircleTemp_views[i].actual != null) {
          tempValue = Math.round(this.semiCircleTemp_views[i].actual) + 'º';
        }
        this.$el.find(search).find('.all-temps').text(tempValue);
      }

    }
    for (var i = 0; i <= this.extruders_count; i++) {
      this._setCircleProgress(i);
    }
  },
  _setCircleProgress: function(index) {
    this.$("#"+this.semiCircleTemp_views[index].el.id+" .progress-temp-circle").circleProgress({
      //value: temps.current,
      arcCoef: 0.55,
      size: 180,
      thickness: 20,
      fill: { gradient: ['#60D2E5', '#E8A13A', '#F02E19'] }
    });
  },
  show: function()
  {
    var semiCircleCount = Object.keys(this.semiCircleTemp_views).length;

    if ( semiCircleCount ) {
      var socketTemps = app.socketData.attributes.temps;

      for (var i = 0; i < semiCircleCount; i++) {
        if (i != this.extruders_count) {
          if (_.has(socketTemps, 'extruders')) {
            temps = {current: socketTemps.extruders[i].current, target: socketTemps.extruders[i].target};
          } else {
            temps = {current: null, target: null};
          }
        } else {
          if (_.has(socketTemps, 'bed')) {
            temps = {current: socketTemps.bed.actual, target: socketTemps.bed.target};
          } else {
            temps = {current: null, target: null};
          }
        }

        if ($("#utilities-view").hasClass('print-paused')) {
          this.semiCircleTemp_views[i].enableTurnOff(false);
        } else {
          this.semiCircleTemp_views[i].enableTurnOff(true);
        }

        this.semiCircleTemp_views[i].updateValues(temps);
      }

      var currentTool = app.socketData.attributes.tool;
      if (currentTool != null) {
        this.currentToolChanged(currentTool);
      }

    }
  },
  getCurrentSelectedSliders: function() {
    return parseInt((this.$('#slider-nav').find('.current-slide').attr('id')).substring(5));
  },
  setCurrentSelectedSliders: function(extruderId) {
    this.$('#slider-nav').find('.current-slide').removeClass('current-slide');
    this.$('#slider').find('.current-slide').removeClass('current-slide');
    this.$('#tool'+extruderId).addClass('current-slide');
    this.$('#temp-'+extruderId).addClass('current-slide');
  },
  currentToolChanged: function(extruderId) {
    this.setCurrentSelectedSliders(extruderId);
    this.scrollSlider(extruderId);
    this.checkedArrows(extruderId);
  },
  navExtruderClicked: function(e) {
    var target = $(e.currentTarget);
    var extruderId = (target.attr('id')).substring(5);
    this.currentToolChanged(extruderId);
  },
  semiCircleTempsClicked: function(e) {
    var target = $(e.currentTarget);
    var elementId = target.attr('id');

    if (elementId != 'bed') {
      var extruderId = (elementId).substring(4);
      this.currentToolChanged(extruderId);
    }
  },
  arrowClicked: function(e) {
    var target = $(e.currentTarget);
    var action = target.attr('id');
    var extruderId = this.getCurrentSelectedSliders();

    if (action == 'previous' && extruderId > 0) {
      extruderId = (extruderId > 0) ? extruderId - 1 : extruderId;
    } else if (action == 'next' && (extruderId+1) < this.extruders_count) {
      extruderId = (extruderId < this.extruders_count) ? extruderId + 1 : extruderId;
    } else {
      target.addClass('arrow-disabled');
    }
    this.currentToolChanged(extruderId);
  },
  scrollSlider: function(extruderId) {
    var scrollWidthSlider = this.$("#slider")[0].scrollWidth;
    var scrollWidthSliderNav = this.$("#slider-nav")[0].scrollWidth;

    this.$("#slider").animate({scrollLeft: ((scrollWidthSlider/this.extruders_count) * extruderId - 1)});
    this.$("#slider-nav").animate({scrollLeft: ((scrollWidthSliderNav/this.extruders_count) * extruderId - 1)});
  },
  checkedArrows: function(extruderId) {
    if (extruderId > 0) {
      this.$('#previous').removeClass('arrow-disabled');
    } else {
      this.$('#previous').addClass('arrow-disabled');
    }

    if (extruderId < (this.extruders_count-1)) {
      this.$('#next').removeClass('arrow-disabled');
    } else {
      this.$('#next').addClass('arrow-disabled');
    }
  }
});

/* Moved control views as widget */

var ExtrusionControlView = Backbone.View.extend({
  el: '#extrusion-control',
  template: null,
  currentTool: null,
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
    this.listenTo(app.socketData, 'change:tool', this.onToolChanged);
    if (this.currentTool == null) {
      this.currentTool = 0;
    }
  },
  render: function()
  {
    var printer_profile = app.printerProfile.toJSON();

    this.$('.row.extruder-switch').html(this.template({
      profile: printer_profile
    }));

    if (this.currentTool != null) {
      this.$('.extruder-number').val(this.currentTool);

      if (this.$('.extruder-number').hasClass('no-selected')) {
        this.$('.extruder-number').removeClass('no-selected');
      }
    }

    if (this.currentTool != this.$('.extruder-number').val()) {
      this.$('.extruder-number').val(this.currentTool);
    }

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
    var selectedTool = $(e.target).val();

    this.setCurrentTool(selectedTool)
    this._sendChangeToolCommand(selectedTool)
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
  },
  setCurrentTool: function(tool) {
    this.currentTool = tool;
  },
  onToolChanged: function(s, value)
  {
    this.setCurrentTool(value);
  }
});

var FanControlView = Backbone.View.extend({
  el: '.fan-control',
  events: {
    'click button.fan-on': "fanOn",
    'click button.fan-off': "fanOff",
    'change .fan-speed': 'speedChanged',
    'change .other-fan-speed input': 'onSpeedFieldChanged'
  },
  fanOn: function()
  {
    var isSpeed0 = false;
    var speedValue = this.$el.find('.fan-speed').val();
    var inputFanSpeed = this.$('input[name="fan-speed"]');

    if (speedValue == 'other') {
      if (inputFanSpeed.val() > 100) {
        inputFanSpeed.val('100');
      } else if (inputFanSpeed.val() <= 0) {
        inputFanSpeed.val('0');
        isSpeed0 = true;
        this.fanOff();
      }
      speedValue = inputFanSpeed.val();
    }

    if (!isSpeed0) {
      var speedClass = '';

      switch(true) {
        case (speedValue <= 25):
            speedClass = 'speed-25';
            break;
        case (speedValue <= 50):
            speedClass = 'speed-50';
            break;
        case (speedValue <= 75):
            speedClass = 'speed-75';
            break;
        default:
            speedClass = 'speed-100';
      }

      this.$('.variable-speed').addClass('animated bounceIn');
      this.$('.variable-speed').one('webkitAnimationEnd mozAnimationEnd MSAnimationEnd oanimationend animationend', function(){
        this.$('.variable-speed').removeClass('bounceIn');
      }.bind(this));

      this._setFanSpeed(speedValue);
      this.$('.fan_icon').addClass('animate-spin');
      this.$('.fan_icon').removeClass (function (index, className) {
          return (className.match (/\bspeed-\S+/g) || []).join(' ');
      });
      this.$('.fan_icon').addClass(speedClass);
      this.$('.fans').removeClass('fan-on').addClass('fan-off');
      this.$('.fans').text('STOP');
    }

  },
  fanOff: function()
  {
    this._setFanSpeed(0);
    this.$('.fan_icon').removeClass('animate-spin');
    this.$('.fans').removeClass('fan-off').addClass('fan-on');
    this.$('.fans').text('START');
  },
  _setFanSpeed: function(speed)
  {
    var data = {
      command: "set",
      tool:  $('#utilities-view #extrusion-control .extruder-number').val(),
      speed: speed
    }

    $.ajax({
      url: API_BASEURL + "printer/fan",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify(data)
    });
  },
  speedChanged: function(e)
  {
    var elem = $(e.target);

    if (elem.val() == 'other') {
      elem.addClass('hide');
      this.$('.other-fan-speed').removeClass('hide').find('input').focus().select();
    } else {
      this.$('input[name="fan-speed"]').val(elem.val());
      this.fanOn();
    }
  },
  onSpeedFieldChanged: function(e) {
    this.fanOn();
    $(e.target).blur();
  }
});

var PrintingSpeedControlView = Backbone.View.extend({
  el: '.printing-speed-control',
  events: {
    'change .printing-speed-amount': 'rateChanged',
    'change .other-printing-speed-amount input': 'onCustomSpeedChanged'
  },
  initialize: function()
  {
    var printingSpeedAmount = app.socketData.attributes.printing_speed;

    this.setSpeedValue(printingSpeedAmount);
  },

  setSpeedValue: function(value)
  {
    if (value == 25 || value == 50 || value == 100 || value == 200 ) {
      this.$('select.printing-speed-amount').val(value).change();
    } else {
      this.$('select.printing-speed-amount').val("other").change();
      this.$('input[name="printing-speed-amount"]').val(value);
    }
  },
  _setPrintSpeed: function(amount)
  {
    var data = {
      command: "set",
      amount: amount
    }

    $.ajax({
      url: API_BASEURL + "printer/printing-speed",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify(data)
    });
  },
  rateChanged: function(e)
  {
    var elem = $(e.target);

    if (elem.val() == 'other') {
      elem.addClass('hide');
      this.$('.other-printing-speed-amount').removeClass('hide').find('input').focus().select();
    } else {
      var amount = elem.val();
      this.$('input[name="printing-speed-amount"]').val(amount);
      this._setPrintSpeed(amount);
    }
  },
  onCustomSpeedChanged: function(e) {
    var elem = $(e.target);
    var amount = elem.val();
    if (amount < 25) { amount = 25; } else if (amount > 500) { amount = 500;}
    elem.val(amount);
    this._setPrintSpeed(amount);
    $(e.target).blur();
  }
});

var PrintingFlowControlView = Backbone.View.extend({
  el: '.printing-flow-control',
  presets: [95,90,100,110,115],
  events: {
    'change .printing-flow-amount': 'rateChanged',
    'change .other-printing-flow-amount input': 'onCustomFlowChanged'
  },
  initialize: function()
  {
    var printingFlowAmount = app.socketData.attributes.printing_flow;

    this.setFlowValue(printingFlowAmount);
  },

  setFlowValue: function(value)
  {
    if (this.presets.indexOf(value) != -1) {
      this.$('select.printing-flow-amount').val(value).change();
    } else {
      this.$('select.printing-flow-amount').val("other").change();
      this.$('input[name="printing-flow-amount"]').val(value);
    }
  },
  _setPrintFlow: function(amount)
  {
    var data = {
      command: "set",
      amount: amount
    }

    $.ajax({
      url: API_BASEURL + "printer/printing-flow",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify(data)
    });
  },
  rateChanged: function(e)
  {
    var elem = $(e.target);

    if (elem.val() == 'other') {
      elem.addClass('hide');
      this.$('.other-printing-flow-amount').removeClass('hide').find('input').focus().select();
    } else {
      var amount = elem.val();
      this.$('input[name="printing-flow-amount"]').val(amount);
      this._setPrintFlow(amount);
    }
  },
  onCustomFlowChanged: function(e) {
    var elem = $(e.target);
    var amount = elem.val();
    if (amount < 50) { amount = 50; } else if (amount > 150) { amount = 150;}
    elem.val(amount);
    this._setPrintFlow(amount);
    $(e.target).blur();
  }
});

var UtilitiesView = Backbone.View.extend({
  el: '#utilities-view',
  events: {
    'click .back': 'back',
    'click .resume,.pause': 'togglePausePrint',
    'show': 'onShow',
    'hide': 'onHide'
  },
  tempView: null,
  extrusionView: null,
  fanView: null,
  printSpeedView: null,
  currentTool: null,
  initialize: function()
  {
    this.tempView = new TempView();
    this.controlView = new ControlView();
    this.$el.find('#control-container').append(this.controlView.render());

    this.extrusionView = new ExtrusionControlView();
    this.fanView = new FanControlView();
    this.printSpeedView = new PrintingSpeedControlView();
    this.printFlowView = new PrintingFlowControlView();
    this.currentTool = app.socketData.attributes.tool;

    this.listenTo(app.socketData, 'change:temps', this.updateTemps);
    this.listenTo(app.socketData, 'change:paused', this.onPausedChanged);
    this.listenTo(app.socketData, 'change:tool', this.onToolChanged);
    this.listenTo(app.socketData, 'change:printing', this.onPrintingChanged);
    this.listenTo(app.socketData, 'change:printing_speed', this.onPrintingSpeedChanged);
    this.listenTo(app.socketData, 'change:printing_flow', this.onPrintingFlowChanged);
  },
  updateTemps: function(s, value)
  {
    if (!this.$el.hasClass('hide')) {
      this.tempView.updateTemps(value);
    }
  },
  onPrintingSpeedChanged: function(m, value)
  {
    this.printSpeedView.setSpeedValue(value);
  },
  onPrintingFlowChanged: function(m, value)
  {
    this.printFlowView.setFlowValue(value);
  },
  onPrintingChanged: function(s, isPrinting)
  {
    if (!isPrinting) {
      this.$el.removeClass('print-active print-paused')
    }
  },
  back: function()
  {
    app.router.navigate("printing", {replace: true, trigger: true});
  },
  onShow: function()
  {
    this.listenTo(app.socketData, 'change:printing_progress', this.onPrintingProgressChanged);
    if (this.currentTool != null && this.extrusionView.currentTool != this.currentTool) {
      this.extrusionView.setCurrentTool(this.currentTool);
    }
    this.onPausedChanged(app.socketData, app.socketData.get('paused'));

    this.extrusionView.render();
  },
  onHide: function()
  {
    this.stopListening(app.socketData, 'change:printing_progress', this.onPrintingProgressChanged);
  },
  togglePausePrint: function(e)
  {
    var loadingBtn = $(e.target).closest('.loading-button');
    var wasPaused = app.socketData.get('paused');

    loadingBtn.addClass('loading');
    this._jobCommand('pause', null, function (data) {
      if (data && _.has(data, 'error')) {
        console.error(data.error);
      } else {
        app.socketData.set('paused', !wasPaused);
      }
      loadingBtn.removeClass('loading');
    });
  },
  onPrintingProgressChanged: function(model, printingProgress)
  {
    if (printingProgress) {
      this.updatePrintingContainer(printingProgress.printFileName, printingProgress.percent)
    }
  },
  onPausedChanged: function(model, paused)
  {
    var printingProgress = model.get('printing_progress');
    if (printingProgress) {
      this.updatePrintingContainer(printingProgress.printFileName, printingProgress.percent);
    }

    if (paused) {
      this.$el.addClass('print-paused');
      this.$el.removeClass('print-active');
    } else {
      if (app.socketData.get('printing')) {
        this.$el.addClass('print-active');
        this.$el.removeClass('print-paused');
      } else {
        this.$el.removeClass('print-paused print-active');
        this.stopListening(app.socketData, 'change:printing_progress', this.onPrintingProgressChanged);
      }
    }
  },
  updatePrintingContainer: function(filename, progress)
  {
    // File name
    if (filename) {
      var nameEl = this.$('.progress .filename');
      if (filename != nameEl.text()) {
        nameEl.text(filename)
      }
    }

    // Progress bar
    this.$('.progress .progress-label').text(progress+"%");
    this.$('.progress .meter').css('width', progress+"%");
  },
  onToolChanged: function(s, value)
  {
    if (value != null) {
      if (this.currentTool != value ){
        this.currentTool = value;
        this.tempView.currentToolChanged(value);
      }

      if (!(this.$('.extruder-number').val() == value)) {
        this.extrusionView.setCurrentTool(value);
        this.extrusionView.render();
        this.$('.extruder-number').val(value);

        if (this.$('.extruder-number').hasClass('no-selected')) {
          this.$('.extruder-number').removeClass('no-selected');
        }
      }
    }
  },
  _jobCommand: function(command, data, callback)
  {
    $.ajax({
      url: API_BASEURL + "job",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify(_.extend({command: command}, data))
    }).
    done(function(data){
      if (callback) callback(data);
    }).
    fail(function(error) {
      if (callback) callback({error:error.responseText});
    });
  },
});
