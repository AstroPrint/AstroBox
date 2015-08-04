var TerminalView = Backbone.View.extend({
  el: '#terminal-view',
  outputView: null,
  events: {
    'submit form': 'onSend',
    'show': 'onShow',
    'hide': 'onHide'
  },
  initialize: function()
  {
    this.outputView = new OutputView();

    app.eventManager.on("astrobox:PrinterResponse", _.bind(function(data) {
      this.outputView.add('received', data)
    }, this));
  },
  onSend: function(e)
  {
    e.preventDefault()

    var sendField = this.$('input');
    var loadingBtn = this.$('button.send').closest('.loading-button');
    var command = sendField.val();

    loadingBtn.addClass('loading');

    $.ajax({
      url: API_BASEURL + 'printer/comm/send',
      method: 'POST',
      data: {
        'command': command
      }
    })
      .done(_.bind(function(){
        this.outputView.add('sent', command);
      }, this))
      .fail(function(){
        loadingBtn.addClass('error');

        setTimeout(function(){
          loadingBtn.removeClass('error');
        }, 3000);
      })
      .always(function(){
        loadingBtn.removeClass('loading');
        sendField.val('');
      });

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
  }
});

var OutputView = Backbone.View.extend({
  el: '#terminal-view .output-container',
  add: function(type, text)
  {
    switch(type) {
      case 'sent':
        text = '<div class="sent bold">'+text+'</div>';
      break;

      case 'received':
        text = '<div class="received">'+text+'</div>';
      break;
    }

    this.$el.append(text);
    this.$el.scrollTop(this.$el[0].scrollHeight);
  }
})
