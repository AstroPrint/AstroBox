/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var HomeView = Backbone.View.extend({
	el: '#home-view',
	uploadView: null,
	initialize: function(options) 
	{
		this.uploadView = new UploadView({el: this.$el.find('.file-upload-view')});
	}
});