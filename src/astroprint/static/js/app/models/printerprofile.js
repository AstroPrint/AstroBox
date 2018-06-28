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
    'invert_z': false,
    'invert_y': false,
    'invert_x': false,
    'temp_presets' : [
      { 'id' : "3e0fc9b398234f2f871310c1998aa000",
      'name' : "PLA",
      'nozzle_temp' : 220,
      'bed_temp' : 40},
       {'id' : "2cc9df599f3e4292b379913f4940c000s",
      'name': "ABS",
      'nozzle_temp': 230,
      'bed_temp' : 80}
    ],
    'last_presets_used' : [
    ]
	}
});
