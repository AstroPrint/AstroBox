var TempSemiCircleView = Backbone.View.extend({
  className: 'semi-circle-temps',
  type: null,
  lastSent: null,
  lastSentTimestamp: null,
  target: 0,
  actual: 0,
  waitAfterSent: 2000, //During this time, ignore incoming target sets
  template: _.template( $("#semi-circle-template").html() ),
  enableOff: true,
  events: {
    'click button.temp-off': 'turnOff',
    'click .temp-target button.temp-edit': 'onEditClicked',
    'change .temp-target input': 'onTempFieldChanged',
    'blur .temp-target input': 'onTempFieldBlur'
  },
  initialize: function(params)
  {
    var tool = params.tool;
    this.enableOff = params.enableOff;

    if (tool != null) {
      this.type = 'tool';
      this.$el.attr('id', 'tool'+tool);

    } else {
      this.type = 'bed';
      this.$el.attr('id', 'bed');
    }
    this.$el.attr('align', 'center');
  },
  render: function ()
  {
    this.$el.html(this.template());

    if (this.type == 'bed') {
      if (!(app.printerProfile.toJSON()).heated_bed) {
        this.$el.find('.temp-off').attr('disabled','disabled');
        this.$el.find('.temp-edit').attr('disabled','disabled');
      }
    }

    this.enableTurnOff(this.enableOff);
    return this;
  },
  onTempFieldBlur: function(e)
  {
    var input = $(e.target);

    input.addClass('hide');
    input.closest('.temp-target').find('button.temp-edit').removeClass('hide');

  },
  updateValues: function (temps)
  {
    if (this.$(".progress-temp-circle").length && temps.current) {
      if (this.type == 'bed') {
        if ((app.printerProfile.toJSON()).heated_bed) {
          this.$(".progress-temp-circle").circleProgress('value', Math.round((temps.current / app.printerProfile.get('max_bed_temp')) * 100) / 100 );
        } else {
          this.$(".progress-temp-circle").circleProgress('value', null );
        }
      } else {
        this.$(".progress-temp-circle").circleProgress('value', Math.round((temps.current / app.printerProfile.get('max_nozzle_temp')) * 100) / 100 );
      }

      var now = new Date().getTime();

      if (this.lastSent !== null && this.lastSentTimestamp > (now - this.waitAfterSent) ) {
        target = this.lastSent;
      }

      if (isNaN(temps.current)) {
        temps.current = null;
      }

      if (isNaN(temps.target)) {
        temps.target = null;
      }

      this.target = temps.target;
      this.actual = temps.current;
      this.setTemps(temps.current, temps.target);
    }
  },
  turnOff: function(e)
  {
    var turnOffButton = $(e.currentTarget);
    if (!turnOffButton.hasClass("animate-spin")) {
      turnOffButton.addClass("animate-spin");

      this._sendToolCommand('target', this.el.id, 0);

      var target = this.$el.find('.temp-target');
      target.find('span.target-value').html(0+'&deg;');

    }
  },
  onEditClicked: function(e)
  {
    e.preventDefault();

    var target = $(e.currentTarget);
    var container = target.closest('.temp-target');
    var label = container.find('span.target-value');
    var button = container.find('button.temp-edit');
    var input = container.find('input');

    button.addClass('hide');
    input.removeClass('hide');
    input.val((label.text()).slice(0, -1));
    setTimeout(function(){input.focus().select()},100);
  },
  onTempFieldChanged: function(e)
  {
    var input = $(e.target);
    var value = input.val();
    var maxValue = null;

    if(this.type == 'bed') {
      maxValue = app.printerProfile.get('max_bed_temp');
    } else {
      maxValue = app.printerProfile.get('max_nozzle_temp');
    }

    if (value < 0) {
      value = 0;
    } else if (value > maxValue) {
      value = maxValue;
    }

    if (value != this.lastSent && !isNaN(value) ) {
      var loadingBtn = this.$('.temp-edit');
      loadingBtn.addClass('loading');
      this._sendToolCommand('target', this.el.id, value);
      input.blur();
    }
  },
  setTemps: function(actual, target)
  {
    var now = new Date().getTime();

    if (this.lastSent !== null && this.lastSentTimestamp > (now - this.waitAfterSent) ) {
      target = this.lastSent;
    }

    if (isNaN(actual)) {
      actual = null;
    }

    if (isNaN(target)) {
      target = null;
    }

    this.target = target;
    this.actual = actual;

    this.renderTemps(actual, target);
  },
  renderTemps: function(actual, target)
  {
    if (actual !== null) {
      this.$el.find('.current').html(Math.round(actual)+'&deg;');
    }

    if (target !== null) {

      var turnOffButton = this.$el.find('.temp-off');
      if (turnOffButton.hasClass("animate-spin")) {
        turnOffButton.removeClass("animate-spin");
      }

      var loadingBtn = this.$('.temp-edit');
      if(loadingBtn.hasClass('loading') ){
        loadingBtn.removeClass('loading');
      }

      this.$el.find('.target-value').html(Math.round(target)+'&deg;');

      if ( this.type == 'bed') {
        var bedTarget = target;
        if (!(app.printerProfile.toJSON()).heated_bed) {
          bedTarget = 0;
        }

        this.$el.find('.target-selector').css({
          transform:'rotate('+ (bedTarget *(198/app.printerProfile.get('max_bed_temp'))-9) +'deg)'});

      } else {
        this.$el.find('.target-selector').css({
          transform:'rotate('+ (target *(198/app.printerProfile.get('max_nozzle_temp'))-9) +'deg)'});
      }
    }
  },
  _sendToolCommand: function(command, type, temp, successCb, errorCb)
  {
    if (temp == this.lastSent) return;

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

    this.lastSentTimestamp = new Date().getTime();
    this.lastSent = temp;
  },
  enableTurnOff: function(value)
  {
    if (value) {
      this.$el.find('.container-off').removeClass('hide');
    } else {
      this.$el.find('.container-off').addClass('hide');
    }
  }
});
