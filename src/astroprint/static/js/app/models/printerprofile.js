/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var PrinterProfile = Backbone.Model.extend({
 	url: API_BASEURL + "printer-profile",
	defaults: {
		'id': 'profile',
		'extruder_count': 2,
		'heated_bed': true
	}
});