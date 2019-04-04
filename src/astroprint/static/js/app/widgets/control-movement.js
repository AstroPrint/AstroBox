/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* global */

/* exported ControlView  */

var ControlView = Backbone.View.extend({
  commandsSender: null,
  distanceSelected: 10,
  babystepAmountSelected: 0.005,
  template: _.template( $("#control-template").html() ),
  ignorePrintingStatus: false,
  onlyBabyStep: false,
  events: {
    // XY AXIS
    'click .btn_x_plus': function(){this.plusTapped('x')},
    'click .btn_x_minus': function(){this.minusTapped('x')},
    'click .btn_y_plus': function(){this.plusTapped('y')},
    'click .btn_y_minus': function(){this.minusTapped('y')},
    'click .btn_home_xy': function(){this.homeTapped('xy')},
    // Z AXIS
    'click .btn_z_plus': function(){this.plusTapped('z')},
    'click .btn_z_minus': function(){this.minusTapped('z')},
    'click .btn_home_z': function(){this.homeTapped('z')},
    // Babysteppping
    'click .btn_babystep_z_plus': function(){this.babyStepPlusTapped()},
    'click .btn_babystep_z_minus': function(){this.babyStepMinusTapped()},

    'click #distance-control button': 'selectDistance',
    'change #babystep-control': 'selectBabystepAmount',
  },
  initialize: function (param)
  {
    this.commandsSender = new CommandsSender();
    this.ignorePrintingStatus = param ? param.ignorePrintingStatus : false;
    this.onlyBabyStep = param ? param.onlyBabyStep : false;
  },

  homeTapped: function(axis)
  {
    var dataAxis = "z";

    if (axis != "z") {dataAxis = ['x', 'y']}

    if (!app.socketData.get('paused')) {
      this.commandsSender.sendHomeCommand(dataAxis);
    }
  },

  plusTapped: function (axis)
  {
    this.commandsSender.sendJogCommand(axis, 1, this.distanceSelected);
  },

  minusTapped: function (axis)
  {
    this.commandsSender.sendJogCommand(axis, -1, this.distanceSelected);
  },

  babyStepPlusTapped: function ()
  {
    this.commandsSender.sendBabyStepCommand(this.babystepAmountSelected);
  },
  babyStepMinusTapped: function ()
  {
    this.commandsSender.sendBabyStepCommand("-" + this.babystepAmountSelected);
  },

  selectDistance: function (e)
  {
    var el = $(e.currentTarget);
    var buttonGroup = $(el).parent().parent()

    buttonGroup.find('.success').removeClass('success').addClass('secondary');
    el.addClass('success').removeClass('secondary');

    this.distanceSelected = el.attr('data-value');
  },
  selectBabystepAmount: function (e) {
    var el = $(e.currentTarget);
    this.babystepAmountSelected = el.val()
  },

  render: function ()
  {
    return this.$el.html(this.template({ignorePrintingStatus: this.ignorePrintingStatus, onlyBabyStep: this.onlyBabyStep}));
  }
});

var CommandsSender = Backbone.View.extend({
  printerProfile: null,
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
  },
  sendBabyStepCommand: function(amount)
  {
    var data = {
      "command": "babystepping"
    }
    data['amount'] = +amount

    $.ajax({
      url: API_BASEURL + "printer/printhead",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify(data)
    });
  }
});
