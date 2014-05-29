/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var Design = Backbone.Model.extend({
	defaults: {
		name: '',
		gcodes: []
	}
});

var DesignCollection = Backbone.Collection.extend({
	model: Design,
	url: API_BASEURL + "cloud-slicer/designs",
	find_print_file: function(design_id, print_file_id) {
		var design = this.get(design_id);
		var print_files = design.get('print_files');

		for(var i=0; i < print_files.length; i++) {
			if (print_files[i].id == print_file_id) {
				return print_files[i];
			}
		}
	}
});