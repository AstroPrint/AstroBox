/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var ConnectionView = Backbone.View.extend({
  el: '#connection-view',
  events: {
    'click i.printer': 'printerTapped',
    'click i.server': 'serverTapped',
    'click i.astroprint': 'astroprintTapped',
    'mouseover i': 'onMouseOver',
    'mouseout i': 'onMouseOut',
    'mouseover a.offline': 'onMouseOver',
    'mouseout a.offline': 'onMouseOut'
  },
  socketData: null,
  tooltip: null,
  initialize: function(opts)
  {
    this.socketData = opts.socket;
    this.listenTo(this.socketData, "change:box_reachable", this.onReachableChanged);
  },
  connect: function(clicked)
  {
    var self = this;

    $.ajax({
      url: API_BASEURL + "connection",
      method: "GET",
      dataType: "json",
      success: function(response) {
        if (response.current.state.substr(0,5) == 'Error' || response.current.state == 'Closed' || response.current.state == 'Offline') {
          if (response.current.state.substr(0,5) == 'Error') {
            console.error("Printer connection had error: "+response.current.state);
          }

          var port = response.options.portPreference;

          if (response.options.ports && !_.has(response.options.ports, port)) {
            port = _.keys(response.options.ports)[0]
          }

          if (port) {
            var data = {
              "command": "connect",
              "port": port,
              "baudrate": response.options.baudratePreference,
              "autoconnect": true
            };

            self.setPrinterConnection('blink-animation');
            $.ajax({
              url: API_BASEURL + "connection",
              type: "POST",
              dataType: "json",
              contentType: "application/json; charset=UTF-8",
              data: JSON.stringify(data),
              error: function() {
                self.setPrinterConnection('failed');
                if (clicked) {
                  app.router.navigate('settings/printer-connection', {trigger: true, replace: true});
                  noty({text: 'Check Connection Settings.', type:"information", timeout: 3000});
                }
              }
            });
          } else {
            if (clicked) {
              app.router.navigate('settings/printer-connection', {trigger: true, replace: true});
              noty({text: 'Check Connection Settings.', type:"information", timeout: 3000});
            }
          }

        } else if (response.current.state != 'Connecting') {
          if (response.current.state == 'Printing' || response.current.state == 'Paused') {
            app.setPrinting();

            // If printing and user is not in utilities view, navigate to printing
            if (response.current.state == 'Printing' && !app.router.utilitiesView ) {
              app.router.navigate("printing", {replace: true, trigger: true});
            }
          }

          self.setPrinterConnection('connected');
        } else {
          self.setPrinterConnection('blink-animation');
        }
      }
    });
  },
  disconnect: function()
  {
    $.ajax({
      url: API_BASEURL + "connection",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify({"command": "disconnect"}),
      success: function(response) {
        self.$el.removeClass('connected');
      }
    });
  },
  setServerConnection: function(className)
  {
    var element = this.$el.find('i.server');
    var titleText = '';

    element.removeClass('blink-animation connected failed').addClass(className);

    switch(className) {
      case 'blink-animation':
        titleText = 'Connecting to <b>'+ASTROBOX_NAME+'</b>...';
      break;

      case 'connected':
        titleText = 'Connected to <b>'+ASTROBOX_NAME+'</b>';
      break;

      case 'failed':
        titleText = '<b>'+ASTROBOX_NAME+'</b> is unreachable';
      break;
    }

    if (titleText) {
      element.data('title', titleText);
    }
  },
  setPrinterConnection: function(className)
  {
    var element = this.$el.find('i.printer');
    var titleText = '';

    element.removeClass('blink-animation connected failed').addClass(className);

    switch(className) {
      case 'blink-animation':
        titleText = 'Connecting to printer...';
      break;

      case 'connected':
        titleText = 'Connected to printer';
        $('html').removeClass('no-printer');
      break;

      case 'failed':
        $('html').addClass('no-printer');
        titleText = 'The printer is not connected';
      break;
    }

    if (titleText) {
      element.data('title', titleText);
    }
  },
  setAstroprintConnection: function(className)
  {
    var element = this.$el.find('i.astroprint')
    var titleText = '';

    element.removeClass('blink-animation connected failed').addClass(className);

    switch(className) {
      case 'blink-animation':
        titleText = 'Connecting to the astroprint.com...';
      break;

      case 'connected':
        titleText = 'Connected to astroprint.com';
      break;

      case 'failed':
        titleText = 'Not connected to astroprint.com';
      break;
    }

    if (titleText) {
      element.data('title', titleText);
    }
  },
  printerTapped: function(e)
  {
    e.stopPropagation();

    if ($(e.target).hasClass('failed')) {
      this.connect(true);
    }
  },
  serverTapped: function(e)
  {
    e.stopPropagation();

    if ($(e.target).hasClass('failed')) {
      this.socketData.reconnect();
      this.connect();
    }
  },
  astroprintTapped: function(e)
  {
    e.stopPropagation();

    var icon = $(e.target);
    if (icon.hasClass('failed')) {
      if (LOGGED_USER) {
        icon.addClass('blink-animation');
        $.ajax({
          url: API_BASEURL + "boxrouter",
          method: "POST",
          dataType: "json",
          complete: function(response) {
            icon.removeClass('blink-animation');
          }
        });
      } else {
        $('#login-modal').foundation('reveal', 'open');
      }
    }
  },
  onReachableChanged: function(s, value)
  {
    switch(value) {
      case 'reachable':
        this.setServerConnection('connected');
      break;

      case 'unreachable':
        this.setServerConnection('failed');
      break;

      case 'checking':
        this.setServerConnection('blink-animation');
      break;
    }
  },
  onMouseOver: function(e)
  {
    if ($('html').hasClass('touch')) return;

    var target = $(e.currentTarget);

    if (!this.tooltip) {
      this.tooltip = $('<div class="tooltip radius"><span class="pip"></span><div class="text"></div></div>')
      $('body').append(this.tooltip);
    }

    var position = target.offset();
    var screenWidth = $(document).width();

    var top = position.top + target.height() - 5;
    var right = screenWidth - ( position.left + ( target.outerWidth() / 2 ) + 10);

    this.tooltip
      .css('top', top)
      .css('right', right)
      .css('background', target.css('color'))
      .removeClass('hide')
      .find('.text')
        .html(target.data('title'));

    this.tooltip.find('.pip').css('border-color', 'transparent transparent '+target.css('color')+' transparent');
  },
  onMouseOut: function(e)
  {
    this.tooltip.addClass('hide');
    this.tooltip.find('.text').html('');
  }
});
