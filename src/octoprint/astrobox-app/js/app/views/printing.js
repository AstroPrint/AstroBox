/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@3dagogo.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var PrintingView = Backbone.View.extend({
	el: '#printing-view',
	startPrint: function(filename) {
		console.log('start printing '+gcode_id);
		this.$el.removeClass('hide');
		$('#app').addClass('hide');
	}
});