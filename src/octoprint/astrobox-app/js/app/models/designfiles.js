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
	findGCode: function(designId, gcodeId) {
		var design = this.get(designId);
		var gcodes = design.get('gcodes');

		for(var i=0; i < gcodes.length; i++) {
			if (gcodes[i].id == gcodeId) {
				return gcodes[i];
			}
		}
	}
});