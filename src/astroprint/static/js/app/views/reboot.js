/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var RebootConfirmationModal = Backbone.View.extend({
	el: '#reboot-modal',
	rebootView: null,
	events: {
		'click button.alert': 'onConfirm',
		'click button.secondary': 'close'
	},
	onConfirm: function() 
	{
		this.$el.foundation('reveal', 'close');
		if (!this.rebootView) {
			this.rebootView = new RebootView();
		}

		app.router.selectView(this.rebootView);
		this.rebootView.doReboot();
	},
	open: function() {
		this.$el.foundation('reveal', 'open');
	},
	close: function() {
		this.$el.foundation('reveal', 'close');
	}
});

var RebootView = Backbone.View.extend({
	el: '#reboot-view',
	doReboot: function() {
        $.ajax({
            url: API_BASEURL + "system",
            type: "POST",
            data: {"action": "reboot"},
            success: _.bind(function() {
				setTimeout(_.bind(function() {
					this.$el.addClass('done');
				}, this), 3000);
            }, this),
            error: _.bind(function() {
            	this.$el.find('.icon-refresh').removeClass('animate-spin');
            	noty({text: "There was an error starting reboot sequence.", timeout: 5000});
            }, this)
        });
	}
});