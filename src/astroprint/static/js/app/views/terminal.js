var TerminalView = Backbone.View.extend({
  el: '#terminal-view',
  outputView: null,
  //sourceId: null,
  events: {
    'submit form': 'onSend',
    'show': 'onShow',
    'hide': 'onHide',
    'click button.clear': 'onClear'
  },
  initialize: function()
  {
    this.outputView = new OutputView();
    //this.sourceId = Math.floor((Math.random() * 100000)); //Generate a random sourceId

    app.eventManager.on("astrobox:PrinterTraffic", _.bind(function(data) {
      //if (data.sourceId == this.sourceId) {
        this.outputView.add(data.direction, data.content);
      //}
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
    var command = sendField.val();

    if (/*this.sourceId &&*/ command) {
      var loadingBtn = this.$('button.send').closest('.loading-button');

      loadingBtn.addClass('loading');

      $.ajax({
        url: API_BASEURL + 'printer/comm/send',
        method: 'POST',
        data: {
          //sourceId: this.sourceId,
          command: command
        }
      })
        //.done(_.bind(function(){
        //  this.outputView.add('sent', command);
        //}, this))
        .fail(_.bind(function(){
          loadingBtn.addClass('error');
          this.outputView.add('s', command, true);

          setTimeout(function(){
            loadingBtn.removeClass('error');
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
