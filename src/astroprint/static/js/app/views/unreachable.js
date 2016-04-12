/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var UnreachableView = Backbone.View.extend({
	el: '#unreachable-view',
	events: {
		'click button': 'onCheckClicked'
	},
	initialize: function()
	{
		this.listenTo(app.socketData, 'change:box_reachable', this.onReachableChanged);
	},
	hide: function() 
	{
		this.$el.addClass('hide');
		this.$('.loading-button').removeClass('loading');
		$('#app').removeClass('hide');
	},
	onCheckClicked: function(e) 
	{
		e.preventDefault();
		app.socketData.reconnect();
	},
	onReachableChanged: function(s, value)
	{
		var btn = this.$('.loading-button');

		if (value == 'checking') {
			btn.addClass('loading');
		} else {
			btn.removeClass('loading');
		}
	}
});