var TerminalView = Backbone.View.extend({
  el: '#terminal-view',
  outputView: null,
  ignoreReceived: ['wait'],
  events: {
    'submit form': 'onSend',
    'show': 'onShow',
    'hide': 'onHide',
    'click button.clear': 'onClear',
    'click .alert-box.warning a': 'onDismissAlert'
  },
  initialize: function()
  {
    this.outputView = new OutputView();

    app.eventManager.on("astrobox:commsData", _.bind(function(data) {
      if ( !(data.direction == 'r' && _.contains(this.ignoreReceived, data.data)) ) {
        this.outputView.add(data.direction, data.data);
      }
    }, this));
  },
  onClear: function(e)
  {
    e.preventDefault();

    this.outputView.clear();
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
  onShow: function()
  {
    this.$('input').focus();
    $.ajax({
      url: API_BASEURL + 'printer/comm/listen',
      method: 'POST'
    })
  },
  onHide: function()
  {
    $.ajax({
      url: API_BASEURL + 'printer/comm/listen',
      method: 'DELETE'
    });
  },
  onDismissAlert: function(e)
  {
    e.preventDefault();

    this.$('.alert-box.warning').remove();
  }
});

var OutputView = Backbone.View.extend({
  el: '#terminal-view .output-container',
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

    this.$el.append(text);
    this.$el.scrollTop(this.$el[0].scrollHeight);
  },
  clear: function()
  {
    this.$el.html('');
  }
});
