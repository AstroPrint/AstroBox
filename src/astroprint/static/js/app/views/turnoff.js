/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var TurnoffConfirmationModal = Backbone.View.extend({
  el: '#turnoff-modal',
  turnoffView: null,
  events: {
    'click button.alert': 'onConfirm',
    'click button.secondary': 'close'
  },
  onConfirm: function()
  {
    this.$el.foundation('reveal', 'close');
    if (!this.turnoffView) {
      this.turnoffView = new TurnoffView();
    }

    app.router.selectView(this.turnoffView);
    this.turnoffView.doTurnoff();
  },
  open: function() {
    this.$el.foundation('reveal', 'open');
  },
  close: function() {
    this.$el.foundation('reveal', 'close');
  }
});

var TurnoffView = Backbone.View.extend({
  el: '#turnoff-view',
  doTurnoff: function() {
    $.ajax({
      url: API_BASEURL + "system",
      type: "POST",
      data: {"action": "shutdown"}
    })
      .done(_.bind(function() {
        setTimeout(_.bind(function() {
          this.$el.addClass('done');
          this.$el.find('.icon-off').removeClass('blink-animation');
        }, this), 6000);
      }, this))
      .fail(_.bind(function() {
        this.$el.find('.icon-off').removeClass('blink-animation');
        noty({text: "There was an error starting turn off sequence.", timeout: 5000});
        this.$el.removeClass('active').addClass('hide');
        $('#app').removeClass('hide');
      }, this));
  }
});
