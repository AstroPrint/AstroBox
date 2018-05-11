var ControlView = Backbone.View.extend({
  commandsSender: null,
  distanceSelected: 10,
  template: _.template( $("#control-template").html() ),
  ignorePrintingStatus: false,
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
    'click button': 'selectDistance'
  },
  initialize: function (param)
  {
    this.commandsSender = new CommandsSender();
    this.ignorePrintingStatus = param ? param.ignorePrintingStatus : false;
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

  selectDistance: function (e)
  {
    var el = $(e.currentTarget);
    this.$el.find('.success').removeClass('success').addClass('secondary');
    el.addClass('success').removeClass('secondary');

    this.distanceSelected = el.attr('data-value');
  },

  render: function ()
  {
    return this.$el.html(this.template({ignorePrintingStatus: this.ignorePrintingStatus}));
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
  }
});
