var TerminalView = Backbone.View.extend({
  el: '#terminal-view',
  outputView: null,
  gcodeTerminalView: null,
  events: {
    'show': 'onShow',
    'hide': 'onHide'
  },
  initialize: function()
  {
    this.gcodeTerminalView = new GcodeWidgetView();
    this.$el.find('#gcode-terminal').append(this.gcodeTerminalView.render());
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
});
