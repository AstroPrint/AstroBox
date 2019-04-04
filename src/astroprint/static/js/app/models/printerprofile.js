/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* exported PrinterProfile */

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
    'printer_model': {
      'id': null,
      'name': null
    },
    'filament': {
      'color': null,
      'name': null
    },
    'temp_presets' : {
      '3e0fc9b398234f2f871310c1998aa000' :
      {
        'name' : "PLA",
        'nozzle_temp' : 220,
        'bed_temp' : 40
      },
      '2cc9df599f3e4292b379913f4940c000' :
      {
        'name': "ABS",
        'nozzle_temp': 230,
        'bed_temp': 80
      }
    },
    'last_presets_used' : {}
	}
});
