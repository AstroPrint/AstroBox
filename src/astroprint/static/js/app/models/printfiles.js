/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var PrintFile = Backbone.Model.extend({
	defaults: {
		'name': '',
		'images':[]
	}
});

var PrintFileCollection = Backbone.Collection.extend({
	model: PrintFile,
	url: API_BASEURL + "astroprint/print-files"
});