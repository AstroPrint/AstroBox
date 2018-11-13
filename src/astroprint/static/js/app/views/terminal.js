var TerminalView = Backbone.View.extend({
  el: '#terminal-view',
  outputView: null,
  gcodeTerminalView: null,
  events: {
    'hide': 'onHide',
    'show': 'onShow',
  },
  initialize: function()
  {
    this.gcodeTerminalView = new GcodeWidgetView();
    this.$el.find('#gcode-terminal').append(this.gcodeTerminalView.render());
  },
  onHide: function()
  {
    this.gcodeTerminalView.stopListening();
  },
  onShow: function()
  {
    this.gcodeTerminalView.startListening();
  }
});
