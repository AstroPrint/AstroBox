/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* global GcodeWidgetView */

/* exported TerminalView */

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
