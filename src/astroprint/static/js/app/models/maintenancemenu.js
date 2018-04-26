/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var MaintenanceMenu = Backbone.Model.extend({

 });

 var MaintenanceMenuCollection = Backbone.Collection.extend({
  model: MaintenanceMenu,
  url: API_BASEURL + "maintenance-menu",
  comparator: function(item) {
    return item.get('type');
  }
});
