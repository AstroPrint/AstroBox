/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var PrinterProfile = Backbone.Model.extend({
 	url: API_BASEURL + "printer-profile",
	defaults: {
		'id': 'profile',
		'extruder_count': 1,
		'max_nozzle_temp': 280,
		'max_bed_temp': 140,
		'heated_bed': true,
		'cancel_gcode': null,
		'invert_z': false
	}
});