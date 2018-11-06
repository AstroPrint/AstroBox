var GcodeWidgetView = Backbone.View.extend({
  template: _.template( $("#gcode-terminal-template").html() ),
  outputView: null,
  ignoreReceived: ['wait'],
  gcodeTerminalView: null,
  events: {
    'submit form': 'onSend',
    'show': 'onShow',
    'hide': 'onHide',
    'click button.clear': 'onClear',
    'click .alert-box.warning a': 'onDismissAlert'
  },

  initialize: function(editBlocked)
  {
    app.eventManager.on("astrobox:commsData", _.bind(function(data) {
      if ( !(data.direction == 'r' && _.contains(this.ignoreReceived, data.data)) ) {
        this.add(data.direction, data.data);
      }
    }, this));
    this.startListening();
    this.editBlocked = editBlocked;
  },

  startListening: function ()
  {
    $.ajax({
      url: API_BASEURL + 'printer/comm/listen',
      method: 'POST'
    });
  },

  render: function ()
  {
    return this.$el.html(this.template({editBlocked: this.editBlocked}));
  },

  addGcodeToInput: function (gcode)
  {
    this.$('input').val(gcode)
  },
  add: function(type, text, failed)
  {
    switch(type) {
      case 's': // sent to printer
        text = '<div class="sent bold'+(failed ? ' failed' : '')+'"><i class="icon-'+(failed ? 'attention' : 'angle-right')+'""></i>'+text+(failed ? ' <small>(failed to sent)</small>':'')+'</div>';
      break;

      case 'r': // received from printer
        text = '<div class="received"><i class="icon-angle-left"></i>'+text+'</div>';
      break;
    }
    this.$('.output-container').append(text);
    this.$('.output-container').scrollTop(this.$el[0].scrollHeight);
  },
  clear: function()
  {
    this.$('.output-container').html('');
  },
  onClear: function(e)
  {
    e.preventDefault();

    this.clear();
  },
  onSend: function(e)
  {
    e.preventDefault();
    var sendField = this.$('input');
    var command = sendField.val().toUpperCase();

    if (command) {
      var loadingBtn = this.$('button.send').closest('.loading-button');

      loadingBtn.addClass('loading');

      $.ajax({
        url: API_BASEURL + 'printer/comm/send',
        method: 'POST',
        data: {
          command: command
        }
      })
        .fail(_.bind(function(){
          loadingBtn.addClass('failed');
          this.outputView.add('s', command, true);

          setTimeout(function(){
            loadingBtn.removeClass('failed');
          }, 3000);
        }, this))
        .always(function(){
          loadingBtn.removeClass('loading');
          sendField.val('');
        });
    }

    return false;
  },
  onDismissAlert: function(e)
  {
    e.preventDefault();

    this.$('.alert-box.warning').remove();
  }
});
