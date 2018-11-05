var TerminalView = Backbone.View.extend({
  el: '#terminal-view',
  outputView: null,
  gcodeTerminalView: null,
  events: {
    'hide': 'onHide'
  },
  initialize: function()
  {
    this.gcodeTerminalView = new GcodeWidgetView();
    this.$el.find('#gcode-terminal').append(this.gcodeTerminalView.render());
  },
  onHide: function()
  {
    $.ajax({
      url: API_BASEURL + 'printer/comm/listen',
      method: 'DELETE'
    });
  },
});
