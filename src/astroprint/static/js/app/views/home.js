/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var HomeView = Backbone.View.extend({
	el: '#home-view',
	uploadBtn: null,
	initialize: function()
	{
		this.uploadBtn = new FileUploadCombined({el: "#home-view #app-container .upload-btn .file-upload"});
	}
});