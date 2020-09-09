/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* global */

/* exported ClearBedModal */

var ClearBedModal = Backbone.View.extend({
	el: '#clear-bed-modal',
	clearBedView: null,
	events: {
		'click button.warning': 'onConfirm',
		'click button.secondary': 'close'
	},
	onConfirm: function()
	{
		this.$el.foundation('reveal', 'close');
		if (!this.clearBedView) {
			this.clearBedView = new ClearBedView(this);
		}
    this.clearBedView.clearBed();
    this.$el.foundation('reveal', 'close');
	},
	open: function() {
		this.$el.foundation('reveal', 'open');
	},
	close: function() {
		this.$el.foundation('reveal', 'close');
	}
});

var ClearBedView = Backbone.View.extend({
	el: '#clear-bed-view',
	clearBed: function() {
    $.ajax({
    url: API_BASEURL + "clearbed",
    method: "POST"}).
    fail(function() {
      noty({text: "There was an error cleaning bed", timeout: 5000});
    })
	}
});
