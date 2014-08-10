/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var TurnoffConfirmationModal = Backbone.View.extend({
	el: '#turnoff-modal',
	events: {
		'click button.alert': 'onConfirm',
		'click button.secondary': 'close'
	},
	onConfirm: function() 
	{
		this.$el.foundation('reveal', 'close');
		app.router.navigate("turning-off", {replace: true, trigger: true});
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
		app.router.navigate('turning-off', {trigger: true, replace: true});

        $.ajax({
            url: API_BASEURL + "system",
            type: "POST",
            data: {"action": "shutdown"},
            success: _.bind(function() {
				setTimeout(_.bind(function() {
					this.$el.addClass('done');
					this.$el.find('.icon-off').removeClass('blink-animation');
				}, this), 5000);
            }, this),
            error: _.bind(function() {
            	this.$el.find('.icon-off').removeClass('blink-animation');
            }, this)
        });
	}
});